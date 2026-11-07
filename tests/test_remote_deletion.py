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


# ------------------------------------------- legacy NULL-state witness (F2 defect)
# صف قديم من حذف محلي سابق: الشاهد موجود بس `remote_state=NULL` (مفيش حذف بعيد اتبدأ).
# العيب (F2): `_restore_local` كانت بتعتبر `pre_state is None` = «إحنا اللي كتبنا الشاهد
# في المحاولة دي» ⇒ تشيل الصف كله، فيضيع منع الإحياء ويمكن الشات يترجّع بعدين.
LEGACY_TS = "2026-01-01T00:00:00Z"


def _seed_legacy_witness(db):
    """يحاكي صفًا قديمًا: شاهد حذف محلي موجود بـ `remote_state=NULL`."""
    db.add_watched(CID, "شات", chat_id=1)
    db.delete_conversation(CID, LEGACY_TS)  # حذف محلي بلا نداء بعيد ⇒ remote_state=NULL
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def _remote_updated_at(db, cid=CID):
    row = db._conn.execute(
        "SELECT remote_updated_at FROM deleted_conversations WHERE conversation_id=?", (cid,)
    ).fetchone()
    return None if row is None else row["remote_updated_at"]


def _deleted_at(db, cid=CID):
    row = db._conn.execute(
        "SELECT deleted_at FROM deleted_conversations WHERE conversation_id=?", (cid,)
    ).fetchone()
    return None if row is None else row["deleted_at"]


def test_legacy_null_witness_survives_definite_failure(tmp_path):
    """F2: صف قديم بـ remote_state=NULL لازم ينجو من فشل حذف بعيد مؤكّد (مايتحذفش)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    res = _run(FakeClient(("status", 401)), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is True            # الصف (الشاهد) اتّحفظ
    assert db.remote_deletion_state(CID) is None  # الحالة البعيدة فضلت NULL
    assert _remote_updated_at(db) is None         # الطابع الزمني اتصفّر
    assert db.get_watched(CID) is None            # البيانات المحلية (الحذف) زي ما هي


def test_legacy_null_witness_survives_ambiguous_present(tmp_path):
    """F2: نفس الصف ينجو من نتيجة مبهمة (404) اتأكّد فيها إن الشات لسه موجود بعيدًا."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    res = _run(FakeClient("404", exists=True), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _remote_updated_at(db) is None


def test_legacy_null_witness_preserves_deleted_at(tmp_path):
    """F2: وقت الحذف الأصلي (deleted_at) يفضل زي ما هو بعد الاسترجاع."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    assert _deleted_at(db) == LEGACY_TS
    _run(FakeClient("404", exists=True), db)
    assert _deleted_at(db) == LEGACY_TS


def test_legacy_null_witness_clears_stale_remote_timestamp(tmp_path):
    """F2: لو الصف القديم عليه طابع حذف بعيد عالق، الاسترجاع بيصفّره (مفيش حالة عالقة)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    db.set_remote_deletion_state(CID, None, "2026-02-02T00:00:00Z")  # طابع قديم عالق
    assert _remote_updated_at(db) == "2026-02-02T00:00:00Z"
    _run(FakeClient(("status", 403)), db)
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _remote_updated_at(db) is None


def test_legacy_null_witness_blocks_resurrection_after_failure(tmp_path):
    """F2: بعد الفشل، مسار إحياء غير صريح (worker/outbox) لازم يفضل ممنوع."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _run(FakeClient("404", exists=True), db)
    db.add_watched(CID, "شات", chat_id=1, new_lifecycle=False)  # إحياء غير صريح
    assert db.get_watched(CID) is None


def test_legacy_null_witness_survives_repeated_attempts(tmp_path):
    """F2: محاولات حذف متكرّرة ما تمحوش الشاهد المحفوظ."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    for _ in range(3):
        _run(FakeClient("404", exists=True), db)
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def test_first_deletion_failure_leaves_no_witness(tmp_path):
    """F2: الحالة العادية (مفيش شاهد قبلها) ⇒ فشل أول حذف ما يسيّبش شاهد عالق."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient(("status", 401)), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is False
    assert db.remote_deletion_state(CID) is None


def test_uncertain_witness_preserved_on_present(tmp_path):
    """F2: شاهد بحالة 'uncertain' يفضل محفوظ ويرجع 'uncertain' (مايتحذفش، مايتأكّدش)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, outbox.now_iso())
    db.set_remote_deletion_state(CID, db.REMOTE_UNCERTAIN, outbox.now_iso())
    res = _run(FakeClient("404", exists=True), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN


def test_confirmed_deletion_removes_local_data_atomically(tmp_path):
    """F2: الحذف البعيد المؤكّد يثبّت الحذف المحلي + 'confirmed' في خطوة واحدة."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    res = _run(FakeClient("ok"), db)
    assert res.status == deletion.STATUS_DELETED
    assert db.get_watched(CID) is None
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_reconcile_does_not_resurrect_or_confirm_legacy_null_witness(tmp_path):
    """F2: تسوية الإقلاع ما تلمسش صفًا قديمًا بـ remote_state=NULL (مش معلّق)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    assert CID not in db.list_pending_remote_deletions()
    # حتى لو التحقق بعيدًا رجّع غايب أو موجود، الصف مش معلّق ⇒ ما يتلمسش ولا يتحوّل مؤكّد.
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db))
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert db.get_watched(CID) is None


# --------------------------------------- R1: legacy witness survives reconciliation
# العيب (R1): لو شاهد قديم (remote_state=NULL) اتوسم مؤقتًا 'deleting' (`begin_remote_deletion`)
# وانهارت العملية قبل التسوية، فعند إعادة التشغيل مع بقاء الشات بعيدًا كانت التسوية بتشيل
# الصف بالكامل (`clear_remote_deletion`) ⇒ يضيع منع الإحياء. الإصلاح: التسوية تميّز الشاهد
# اللي سبق المحاولة (بمقارنة `deleted_at` بـ `remote_updated_at`) فتحافظ عليه وتصفّر بيانات
# الحذف البعيد بس. الحالات دي بتستخدم **نفس** `begin_remote_deletion` الحقيقي + `asyncio.run`
# لتسوية الإقلاع (مسار انهيار/إعادة تشغيل فعلي، مش استرجاع داخلي عادي).


def _interrupt_attempt(db):
    """يحاكي انهيار العملية **بعد** وسم المحاولة (نفس النداء اللي الإنتاج بيعمله)."""
    db.begin_remote_deletion(CID, outbox.now_iso())


def test_r1_legacy_witness_survives_restart_reconcile_present(tmp_path):
    """R1/A: شاهد قديم + انهيار بعد 'deleting' + إعادة تشغيل + الشات موجود ⇒ ينجو."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)  # NULL -> deleting ثم انهيار
    assert db.list_pending_remote_deletions() == [CID]
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True                 # الصف نجح (ما اتحذفش)
    assert db.remote_deletion_state(CID) is None      # الحالة رجعت NULL
    assert _deleted_at(db) == LEGACY_TS               # deleted_at الأصلي ما اتغيّرش
    assert _remote_updated_at(db) is None             # الطابع البعيد اتصفّر
    assert db.get_watched(CID) is None                # البيانات المحلية (الحذف) زي ما هي


def test_r1_legacy_witness_survives_restart_reconcile_absent(tmp_path):
    """R1/A: نفس السيناريو بس الشات غايب فعلًا (قراءتان) ⇒ نثبّت الحذف 'confirmed'."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_r1_legacy_witness_survives_restart_reconcile_unverifiable(tmp_path):
    """R1/E: تعذّر التحقق (خطأ قراءة) ⇒ يفضل معلّق والشاهد ينجو (مفيش تخمين)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists_error=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING
    assert CID in db.list_pending_remote_deletions()


def test_r1_legacy_witness_survives_true_restart_reconcile(tmp_path):
    """R1/A (إعادة تشغيل حقيقية): إغلاق القاعدة وإعادة فتحها بعد الوسم، ثم تسوية الإقلاع."""
    path = str(tmp_path / "restart.sqlite3")
    db = Database(path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)      # NULL -> deleting ثم «انهيار» (نقفل العملية)
    db.close()
    db2 = Database(path)        # إعادة تشغيل: اتصال جديد على نفس الملف
    assert db2.remote_deletion_state(CID) == db2.REMOTE_DELETING
    assert db2.list_pending_remote_deletions() == [CID]
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.is_deleted(CID) is True
    assert db2.remote_deletion_state(CID) is None
    assert _deleted_at(db2) == LEGACY_TS
    assert _remote_updated_at(db2) is None


def test_r1_new_witness_restart_reconcile_present_cleared(tmp_path):
    """R1/B: شاهد من محاولة جديدة (مفيش شاهد قبله) + انهيار + موجود ⇒ يتشال (السلوك القديم)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    _interrupt_attempt(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False                # اترجّع محليًا (مفيش شاهد عالق)
    assert db.remote_deletion_state(CID) is None


def test_r1_new_witness_restart_reconcile_absent_confirmed(tmp_path):
    """R1/B: محاولة جديدة + انهيار + غياب ⇒ 'confirmed'."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    _interrupt_attempt(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db))
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_r1_uncertain_fresh_witness_reconcile_present_cleared(tmp_path):
    """R1/C: شاهد 'uncertain' من محاولة جديدة + موجود ⇒ يتشال (السلوك الحالي)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    # مسار الإنتاج: نداء حذف بغياب قراءة ⇒ 'uncertain' بنفس `now` بتاع الوسم.
    _run(FakeClient("404", exists_error=True), db)
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_r1_legacy_witness_reaching_uncertain_is_preserved(tmp_path):
    """R1/C: شاهد قديم يمرّ لـ 'uncertain' عبر المسار الحقيقي + موجود ⇒ ينجو (سبق المحاولة)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    # فشل مبهم + تعذّر التحقق ⇒ 'uncertain' بنفس `now`؛ deleted_at القديم يفضل مختلف.
    _run(FakeClient("404", exists_error=True), db)
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert db.is_deleted(CID) is True
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _deleted_at(db) == LEGACY_TS


def test_r1_is_legacy_witness_predicate(tmp_path):
    """R1: بريديكيت التمييز — محاولة جديدة = False، شاهد قديم = True، مفيش صف = False."""
    db = Database(os.path.join(str(tmp_path), "a.sqlite3"))
    assert db.is_legacy_witness(CID) is False  # مفيش صف
    db.add_watched(CID, "شات", chat_id=1)
    _interrupt_attempt(db)
    assert db.is_legacy_witness(CID) is False   # محاولة جديدة (deleted_at == remote_updated_at)
    db2 = Database(os.path.join(str(tmp_path), "b.sqlite3"))
    _seed_legacy_witness(db2)
    _interrupt_attempt(db2)
    assert db2.is_legacy_witness(CID) is True   # شاهد قديم (deleted_at أقدم)


def test_r1_repeated_reconcile_preserves_legacy_witness(tmp_path):
    """R1/F: تسوية متكرّرة ما تحذفش الشاهد القديم ولا تفسده."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    client = FakeClient(exists=True)
    for _ in range(4):
        asyncio.run(deletion.reconcile_pending_deletions(client, db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _deleted_at(db) == LEGACY_TS
    assert _remote_updated_at(db) is None


def test_r1_concurrent_reconcile_preserves_legacy_witness(tmp_path):
    """R1/F: تسويتان متزامنتان (اتصالان مستقلان) ما يحذفوش الشاهد القديم."""
    import threading

    path = str(tmp_path / "conc.sqlite3")
    db = Database(path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    db2 = Database(path)  # اتصال تاني مستقل على نفس الملف
    barrier = threading.Barrier(2)

    def worker(d):
        barrier.wait()
        asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), d))

    ts = [threading.Thread(target=worker, args=(db,)), threading.Thread(target=worker, args=(db2,))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # في كل الترتيبات، الشاهد القديم بينجو (مايتحذفش أبدًا من مسار «موجود»).
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def test_r1_ambiguous_and_server_errors_do_not_erase_legacy_witness(tmp_path):
    """R1/E: 429/5xx/خطأ قراءة/رد مشوّه ما يمحوش الشاهد القديم ولا يأكّدوا حذفًا كاذبًا."""
    for i, behaviour in enumerate((("status", 429), ("status", 500), ("status", 503), "unknown")):
        db = Database(os.path.join(str(tmp_path), f"a{i}.sqlite3"))
        _seed_legacy_witness(db)
        # الشات لسه موجود (فشل الحذف فعلًا) ⇒ الاسترجاع لازم يحافظ على الشاهد.
        res = _run(FakeClient(behaviour, exists=True), db)
        assert res.status == deletion.STATUS_FAILED, behaviour
        assert db.is_deleted(CID) is True, behaviour
        assert db.remote_deletion_state(CID) is None, behaviour
        # وتعذّر التحقق كذلك ⇒ يفضل معلّق والشاهد موجود (مفيش تأكيد كاذب).
        db2 = Database(os.path.join(str(tmp_path), f"b{i}.sqlite3"))
        _seed_legacy_witness(db2)
        res2 = _run(FakeClient(behaviour, exists_error=True), db2)
        assert res2.status == deletion.STATUS_PENDING, behaviour
        assert db2.is_deleted(CID) is True, behaviour
        assert db2.remote_deletion_state(CID) == db2.REMOTE_UNCERTAIN, behaviour


def test_r1_single_missing_read_does_not_confirm(tmp_path):
    """R1/D: قراءة واحدة غايبة مش دليل ⇒ ممنوع الحذف المحلي (لازم قراءتين متتاليتين)."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    # قراءة أولى غايبة ثم ثانية موجودة ⇒ «موجود» ⇒ الشاهد ينجو (مفيش تأكيد كاذب).
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists_seq=[False, True]), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    # والتأكيد بيتطلب غيابين متتاليين (حرس القراءتين لسه ساري).
    assert deletion._ABSENCE_CONFIRMATIONS == 2


def test_r1_startup_reconcile_blocks_resurrection_before_workers(tmp_path):
    """R1/G: بعد تسوية الإقلاع (الشات موجود)، مسار الإحياء غير الصريح (worker/outbox) ممنوع."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    _interrupt_attempt(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    # الـ workers بيبدأوا بعد التسوية؛ محاولة إحياء غير صريحة لازم تترفض بسبب الشاهد.
    db.add_watched(CID, "شات", chat_id=1, new_lifecycle=False)
    assert db.get_watched(CID) is None


# --------------------------------------- F1: retry must not flip witness classification
# العيب (F1): شاهد **جديد** بيدخل حالة 'uncertain' بنفس الطابع (`deleted_at == remote_updated_at`).
# لو إعادة محاولة فشلت فشلًا مؤكّدًا، `_restore_local` كانت بتكتب `remote_updated_at = now`
# **جديد** ⇒ يبقى `deleted_at != remote_updated_at` ⇒ الشاهد الجديد يبان «قديم»، فتسوية لاحقة
# مع «الشات لسه موجود» **تحافظ** على الصف بدل ما تشيله (صف شاهد زائد). الإصلاح: الاسترجاع
# يرجّع **الحالة والطابع الأصليين بالظبط** (`pre_updated_at`) بدل توليد طابع جديد.


def _seed_uncertain_new_witness(db):
    """شاهد من محاولة جديدة انتهت 'uncertain' (نفس الطابع للحقلين زي الإنتاج)."""
    db.add_watched(CID, "شات", chat_id=1)
    now = outbox.now_iso()
    db.begin_remote_deletion(CID, now)
    db.set_remote_deletion_state(CID, db.REMOTE_UNCERTAIN, now)
    assert db.is_legacy_witness(CID) is False


def test_f1_new_witness_uncertain_retry_definite_failure_reconcile_clears(tmp_path):
    """F1/A: شاهد جديد → 'uncertain' → إعادة محاولة فشل مؤكّد → الشات موجود ⇒ التسوية تشيله."""
    db = _db(tmp_path)
    # call1: فشل مبهم + تعذّر التحقق ⇒ 'uncertain' (طابع واحد للحقلين).
    assert _run(FakeClient("404", exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert _deleted_at(db) == _remote_updated_at(db)  # شاهد جديد
    assert db.is_legacy_witness(CID) is False
    # call2 (إعادة محاولة): فشل مؤكّد ⇒ لازم يفضل **جديد** (الطابع ما يتغيّرش).
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    assert db.is_legacy_witness(CID) is False, "إعادة المحاولة حوّلت الشاهد الجديد لقديم (F1)"
    assert _remote_updated_at(db) == _deleted_at(db)
    # تسوية مع «الشات لسه موجود» ⇒ الشاهد الجديد يتشال.
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1_new_witness_uncertain_retry_ambiguous_present_reconcile_clears(tmp_path):
    """F1/A: نفس السيناريو بس إعادة المحاولة مبهمة + الشات موجود ⇒ برضه يتشال."""
    db = _db(tmp_path)
    assert _run(FakeClient("404", exists_error=True), db).status == deletion.STATUS_PENDING
    assert _run(FakeClient("404", exists=True), db).status == deletion.STATUS_FAILED
    assert db.is_legacy_witness(CID) is False
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1_legacy_witness_retry_definite_failure_survives(tmp_path):
    """F1/B: شاهد قديم → إعادة محاولة فشل مؤكّد → الشات موجود ⇒ الشاهد القديم ينجو."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _deleted_at(db) == LEGACY_TS
    assert _remote_updated_at(db) is None
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _deleted_at(db) == LEGACY_TS


def test_f1_legacy_witness_explicit_prior_state_restored_exactly(tmp_path):
    """F1/C: شاهد بحالة سابقة صريحة ('deleting' بطابع قديم) ⇒ الاسترجاع يرجّعها **بالظبط**."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    prev_ts = "2026-02-02T00:00:00Z"
    db.set_remote_deletion_state(CID, db.REMOTE_DELETING, prev_ts)  # محاولة سابقة انقطعت
    assert _remote_updated_at(db) == prev_ts
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING
    assert _remote_updated_at(db) == prev_ts          # ما اتولّدش طابع جديد
    assert _deleted_at(db) == LEGACY_TS


def test_f1_new_witness_classification_stable_across_repeated_retries(tmp_path):
    """F1/D: تصنيف الشاهد الجديد يفضل ثابت عبر إعادات محاولة متكرّرة."""
    db = _db(tmp_path)
    _seed_uncertain_new_witness(db)
    for _ in range(4):
        assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
        assert db.is_legacy_witness(CID) is False
        assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
        assert _remote_updated_at(db) == _deleted_at(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1_restart_between_retry_and_reconcile(tmp_path):
    """F1/E: إغلاق/إعادة فتح القاعدة بين إعادة المحاولة والتسوية ما يغيّرش النتيجة."""
    path = str(tmp_path / "f1restart.sqlite3")
    db = Database(path)
    _seed_uncertain_new_witness(db)
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    db.close()
    db2 = Database(path)
    assert db2.is_legacy_witness(CID) is False
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.is_deleted(CID) is False


def test_f1_legacy_witness_restart_between_retry_and_reconcile(tmp_path):
    """F1/E: نفس الإعادة للشاهد القديم ⇒ يفضل محفوظ بعد إعادة التشغيل."""
    path = str(tmp_path / "f1legacy.sqlite3")
    db = Database(path)
    _seed_legacy_witness(db)
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    db.close()
    db2 = Database(path)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.is_deleted(CID) is True
    assert db2.remote_deletion_state(CID) is None
    assert _deleted_at(db2) == LEGACY_TS


def test_f1_ambiguous_retry_keeps_pending_no_false_confirm(tmp_path):
    """F1/H: إعادة محاولة مبهمة + تعذّر التحقق ⇒ 'pending'/'uncertain' (مفيش تأكيد كاذب)."""
    db = _db(tmp_path)
    _seed_uncertain_new_witness(db)
    res = _run(FakeClient(("status", 503), exists_error=True), db)
    assert res.status == deletion.STATUS_PENDING
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN


def test_f1_remote_deletion_metadata_helper(tmp_path):
    """F1: مساعد القراءة المزدوجة يرجّع (الحالة، الطابع) في قراءة واحدة؛ و(None,None) لو مفيش صف."""
    db = _db(tmp_path)
    assert db.remote_deletion_metadata(CID) == (None, None)
    _seed_legacy_witness(db)
    db.set_remote_deletion_state(CID, db.REMOTE_DELETING, "2026-03-03T00:00:00Z")
    assert db.remote_deletion_metadata(CID) == (db.REMOTE_DELETING, "2026-03-03T00:00:00Z")


# ------------------------------- F1-R: unverifiable retry must not flip witness classification
# العيب (F1-R): إعادة محاولة **مبهمة** + تعذّر التحقق تمرّ بـ `_reconcile` فرع `absent is None`
# اللي كان بيسجّل 'uncertain' بطابع `now` الجديد ⇒ `remote_updated_at != deleted_at` ⇒ الشاهد
# الجديد يُصنَّف «قديم»، فتسوية لاحقة مع «الشات لسه موجود» **تحافظ** عليه بدل ما تشيله.
# الإصلاح: نمرّر `pending_ts` = طابع ما قبل المحاولة (لو موجود) وإلا `now`، فيفضل التصنيف.


def _seed_new_uncertain(db):
    """شاهد من محاولة جديدة وصلت 'uncertain' (نفس الطابع للحقلين زي الإنتاج)."""
    db.add_watched(CID, "شات", chat_id=1)
    now = outbox.now_iso()
    db.begin_remote_deletion(CID, now)
    db.set_remote_deletion_state(CID, db.REMOTE_UNCERTAIN, now)
    assert db.is_legacy_witness(CID) is False


def test_f1r_p1_new_witness_unverifiable_retry_then_present_clears(tmp_path):
    """F1-R/P1: شاهد جديد → 'uncertain' → إعادة محاولة مبهمة + تعذّر التحقق → الشات موجود ⇒ يُشال."""
    db = _db(tmp_path)
    assert _run(FakeClient("404", exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.is_legacy_witness(CID) is False
    deleted_at = _deleted_at(db)
    # إعادة محاولة: نتيجة مبهمة + تعذّر التحقق ⇒ 'pending' لكن **التصنيف لازم يفضل جديد**.
    assert _run(FakeClient(("status", 503), exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.is_legacy_witness(CID) is False, "إعادة محاولة غير قابلة للتحقق حوّلت الشاهد الجديد لقديم (F1-R)"
    assert _deleted_at(db) == deleted_at
    assert _remote_updated_at(db) == deleted_at
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1r_p2_multiple_unverifiable_retries_then_present_clears(tmp_path):
    """F1-R/P2: إعادات محاولة متعدّدة مبهمة/غير قابلة للتحقق ⇒ يفضل جديد ⇒ التسوية تشيله."""
    db = _db(tmp_path)
    assert _run(FakeClient("404", exists_error=True), db).status == deletion.STATUS_PENDING
    deleted_at = _deleted_at(db)
    for _ in range(3):
        assert _run(FakeClient(("status", 500), exists_error=True), db).status == deletion.STATUS_PENDING
        assert db.is_legacy_witness(CID) is False
        assert _deleted_at(db) == deleted_at
        assert _remote_updated_at(db) == deleted_at
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1r_first_attempt_unverifiable_preserves_new_classification(tmp_path):
    """F1-R: أول محاولة على شاهد جديد + تعذّر التحقق ⇒ يفضل جديد (طابع = deleted_at)."""
    db = _db(tmp_path)
    assert _run(FakeClient(("status", 503), exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert db.is_legacy_witness(CID) is False
    assert _remote_updated_at(db) == _deleted_at(db)
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False


def test_f1r_legacy_null_unverifiable_retry_then_present_survives(tmp_path):
    """F1-R: شاهد قديم (NULL) + إعادة محاولة مبهمة/غير قابلة للتحقق ⇒ يفضل قديم وينجو."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    assert _run(FakeClient(("status", 503), exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.is_legacy_witness(CID) is True
    assert _deleted_at(db) == LEGACY_TS
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _remote_updated_at(db) is None
    assert _deleted_at(db) == LEGACY_TS


def test_f1r_legacy_explicit_prior_retry_preserves_metadata(tmp_path):
    """F1-R: شاهد قديم بحالة/طابع صريحين + إعادة محاولة غير قابلة للتحقق ⇒ البيانات محفوظة."""
    db = _db(tmp_path)
    _seed_legacy_witness(db)
    prev_ts = "2026-02-02T00:00:00Z"
    db.set_remote_deletion_state(CID, db.REMOTE_DELETING, prev_ts)
    assert _run(FakeClient(("status", 503), exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.is_legacy_witness(CID) is True
    assert _remote_updated_at(db) == prev_ts
    assert _deleted_at(db) == LEGACY_TS
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _deleted_at(db) == LEGACY_TS


def test_f1r_repeated_retries_classification_survives_restart(tmp_path):
    """F1-R: تصنيف الشاهد الجديد يفضل صحيحًا عبر إعادات متكرّرة **وإغلاق/إعادة فتح القاعدة**."""
    path = str(tmp_path / "f1r.sqlite3")
    db = Database(path)
    _seed_new_uncertain(db)
    deleted_at = _deleted_at(db)
    for _ in range(3):
        assert _run(FakeClient(("status", 503), exists_error=True), db).status == deletion.STATUS_PENDING
    db.close()
    db2 = Database(path)
    assert db2.is_legacy_witness(CID) is False
    assert _deleted_at(db2) == deleted_at
    assert _remote_updated_at(db2) == deleted_at
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.is_deleted(CID) is False


def test_f1r_legacy_restart_after_unverifiable_retry_survives(tmp_path):
    """F1-R: نفس الإعادة لشاهد قديم ⇒ ينجو بعد إعادة التشغيل."""
    path = str(tmp_path / "f1rlegacy.sqlite3")
    db = Database(path)
    _seed_legacy_witness(db)
    assert _run(FakeClient(("status", 500), exists_error=True), db).status == deletion.STATUS_PENDING
    db.close()
    db2 = Database(path)
    assert db2.is_legacy_witness(CID) is True
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.is_deleted(CID) is True
    assert db2.remote_deletion_state(CID) is None
    assert _deleted_at(db2) == LEGACY_TS


def test_f1r_unverifiable_retry_never_confirms_deletion(tmp_path):
    """F1-R: إعادة محاولة غير قابلة للتحقق ما تتحوّلش لتأكيد حذف (تفضل 'uncertain')."""
    db = _db(tmp_path)
    _seed_new_uncertain(db)
    for beh in [("status", 404), ("status", 429), ("status", 500), ("status", 503), "unknown"]:
        res = _run(FakeClient(beh, exists_error=True), db)
        assert res.status == deletion.STATUS_PENDING
        assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
        assert db.is_deleted(CID) is True
