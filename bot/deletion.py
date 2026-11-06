"""تنسيق الحذف **البعيد** لشات OpenHands (OHB2-MINIAPP).

الهدف: الحذف من OpenHands نفسه (مش إخفاء محلي). دورة حياة واحدة مشتركة بين البوت والـ
Mini App — نفس الشواهد ونفس حالات الحذف البعيد في قاعدة البيانات، عشان مايبقاش فيه
مسارين متفرقين.

العقد (مطابق لـ `DELETE /api/v1/app-conversations/{id}` الموثّق):
- 200 `{"success": true}` ⇒ OpenHands أكّد الحذف ⇒ نثبّت 'confirmed' ونسجّل الحذف المحلي.
- 404 ⇒ الشات مش موجود بعيدًا ⇒ نعتبرها نجاح (idempotent).
- 401/403/422 ⇒ فشل مؤكّد (الحذف البعيد **ما حصلش**) ⇒ مفيش نجاح كاذب، ومسار إعادة محاولة.
- 429/5xx/انقطاع/إعادة توجيه/رد مش متوقع ⇒ نتيجة **مجهولة** ⇒ نسوّي بالتحقق من الوجود
  (GET) قبل ما نقرر: مش موجود ⇒ نجاح، موجود ⇒ فشل، تعذّر التحقق ⇒ 'uncertain' (مش نجاح).

قواعد غير قابلة للتفاوض:
- مفيش «نجاح» غير لما OpenHands يأكّد (أو التحقق يثبت الغياب).
- مفيش fallback صامت لحذف محلي فقط.
- الملكية بتتفوّض **قبل** النداء (عند المستدعي)، والنتيجة المجهولة تفضل 'uncertain' (تنجو من restart).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from . import outbox
from .errors import ApiError

log = logging.getLogger(__name__)

STATUS_DELETED = "deleted"   # اتحذف بعيدًا (مؤكّد) + اتحذف محليًا
STATUS_FAILED = "failed"     # فشل مؤكّد: الشات لسه موجود بعيدًا
STATUS_PENDING = "pending"   # نتيجة مجهولة: لسه مش متأكد، محتاج إعادة محاولة/تسوية

DELETED_MESSAGE = "اتحذف الشات نهائيًا من OpenHands ✅"
FAILED_MESSAGE = "تعذّر حذف الشات من OpenHands — الشات لسه موجود. جرّب تاني."
PENDING_MESSAGE = (
    "طلب الحذف اتبعت لـ OpenHands بس لسه مش متأكد إنه خلص. "
    "الشات متقفل محليًا؛ جرّب تاني بعد شوية أو راجع الـ Mini App للتحقق."
)


@dataclass(frozen=True)
class DeletionResult:
    status: str            # STATUS_* فوق
    message: str           # رسالة عربي جاهزة للعرض (مفيش أسرار)
    conversation_id: str
    http_status: int | None = None   # ترميز HTTP لرد الـ Mini App (لو مناسب)
    code: str | None = None          # ترميز خطأ منظّم للواجهة


def _is_definite_failure(status_code: int | None) -> bool:
    """فشل مؤكّد (الحذف البعيد ما حصلش): 4xx من غير 429 (اللي قابل لإعادة المحاولة)."""
    return (
        status_code is not None
        and 400 <= status_code < 500
        and status_code != 429
    )


async def _remote_absent(client, conversation_id: str) -> bool | None:
    """هل الشات اتأكد غيابه بعيدًا؟ True=غايب، False=موجود، None=تعذّر التحقق."""
    try:
        return not await client.conversation_exists(conversation_id)
    except ApiError:
        return None


def _finalize(db, conversation_id: str, now: str) -> DeletionResult:
    """يثبّت الحذف المحلي + حالة 'confirmed' (ذرّي) ويرجّع نتيجة نجاح."""
    db.delete_conversation(conversation_id, now, remote_confirmed=True)
    return DeletionResult(STATUS_DELETED, DELETED_MESSAGE, conversation_id, http_status=200)


async def delete_conversation_remote(client, db, conversation_id: str) -> DeletionResult:
    """يحذف شات من OpenHands ثم يثبّت الحذف محليًا. يتطلب تفويض ملكية مسبق من المستدعي."""
    now = outbox.now_iso()
    pre_state = db.remote_deletion_state(conversation_id)

    # حذف بعيد مؤكّد سابقًا: نعيد تثبيت الحذف المحلي (idempotent) من غير نداء تاني.
    if pre_state == db.REMOTE_CONFIRMED:
        return _finalize(db, conversation_id, now)

    def _restore_local() -> None:
        # الفشل يعني إن طلب المستخدم ما اكتملش ⇒ نرجّع الحالة المحلية زي ما كانت. لو إحنا
        # اللي كتبنا الشاهد في المحاولة دي (مفيش حالة سابقة) نشيله؛ لو كان فيه شاهد قديم
        # (حذف محلي سابق) ما نلمسوش (نشيل وسم الحذف البعيد بس) — ما نكسرش منع الإحياء القديم.
        if pre_state is None:
            db.clear_remote_deletion(conversation_id)
        else:
            db.set_remote_deletion_state(conversation_id, pre_state, now)

    # نوسم الحذف الجاري **قبل** النداء البعيد (شاهد + 'deleting') — ينجو من restart ويمنع
    # أي worker/مسار من إحياء الشات أثناء الحذف.
    db.begin_remote_deletion(conversation_id, now)

    try:
        await client.delete_conversation(conversation_id)
    except ApiError as exc:
        code = exc.status_code
        if code == 404:
            # مش موجود بعيدًا أصلاً ⇒ الهدف اتحقق (idempotent).
            return _finalize(db, conversation_id, now)
        if _is_definite_failure(code):
            # فشل مؤكّد: الحذف البعيد ما حصلش ⇒ نرجّع الحالة المحلية، ونبلّغ فشل صريح —
            # مفيش نجاح كاذب ومفيش إخفاء كاذب.
            _restore_local()
            return DeletionResult(
                STATUS_FAILED, FAILED_MESSAGE, conversation_id,
                http_status=code, code="remote_delete_failed",
            )
        # نتيجة مجهولة (429/5xx/انقطاع/إعادة توجيه/رد مش متوقع): نسوّي بالتحقق من الوجود.
        absent = await _remote_absent(client, conversation_id)
        if absent is True:
            return _finalize(db, conversation_id, now)
        if absent is False:
            # اتأكدنا إن الشات لسه موجود ⇒ الحذف ما حصلش ⇒ نرجّع الحالة المحلية.
            _restore_local()
            return DeletionResult(
                STATUS_FAILED, FAILED_MESSAGE, conversation_id,
                http_status=502, code="remote_delete_failed",
            )
        # تعذّر التحقق ⇒ 'pending' (مش نجاح، ومش فشل مؤكّد).
        db.set_remote_deletion_state(conversation_id, db.REMOTE_UNCERTAIN, now)
        return DeletionResult(
            STATUS_PENDING, PENDING_MESSAGE, conversation_id,
            http_status=503, code="remote_delete_pending",
        )

    # OpenHands أكّد (200 success=true) ⇒ نثبّت الحذف المحلي + 'confirmed'.
    return _finalize(db, conversation_id, now)


async def reconcile_pending_deletions(client, db) -> None:
    """تسوية الحذف البعيد المعلّق بعد restart (best-effort، غير قاتل).

    لكل شات حالته 'deleting'/'uncertain': نتحقق من الوجود بعيدًا.
    - غايب ⇒ نثبّت الحذف (اتحذف فعلًا قبل الانقطاع).
    - موجود ⇒ نرجّعه محليًا (الحذف البعيد ما حصلش؛ مفيش إخفاء كاذب).
    - تعذّر التحقق ⇒ نسيبه معلّق (مفيش تخمين).
    """
    try:
        pending = db.list_pending_remote_deletions()
    except Exception as exc:  # noqa: BLE001 — التسوية ما تمنعش الإقلاع
        log.warning("تعذّر قراءة الحذف البعيد المعلّق (%s)", type(exc).__name__)
        return
    for conversation_id in pending:
        absent = await _remote_absent(client, conversation_id)
        now = outbox.now_iso()
        if absent is True:
            try:
                db.delete_conversation(conversation_id, now, remote_confirmed=True)
                log.info("تسوية: تأكيد حذف بعيد معلّق (%s)", conversation_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("تعذّر تثبيت حذف معلّق (%s)", type(exc).__name__)
        elif absent is False:
            try:
                db.clear_remote_deletion(conversation_id)
                log.info("تسوية: الشات لسه موجود بعيدًا ⇒ رجع محليًا (%s)", conversation_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("تعذّر استرجاع شات معلّق (%s)", type(exc).__name__)
        # absent is None ⇒ نسيبه معلّق (مفيش تخمين).


# الواجهة العامة للوحدة.
__all__ = [
    "DeletionResult",
    "delete_conversation_remote",
    "reconcile_pending_deletions",
    "STATUS_DELETED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "DELETED_MESSAGE",
    "FAILED_MESSAGE",
    "PENDING_MESSAGE",
]
