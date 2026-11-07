"""تنسيق الحذف **البعيد** لشات OpenHands (OHB2-MINIAPP).

الهدف: الحذف من OpenHands نفسه (مش إخفاء محلي). دورة حياة واحدة مشتركة بين البوت والـ
Mini App — نفس الشواهد ونفس حالات الحذف البعيد في قاعدة البيانات، عشان مايبقاش فيه
مسارين متفرقين.

العقد (مطابق لـ `DELETE /api/v1/app-conversations/{id}` الموثّق):
- 200 `{"success": true}` ⇒ OpenHands أكّد الحذف ⇒ نثبّت 'confirmed' ونسجّل الحذف المحلي.
- 404 ⇒ نتيجة **مبهمة**: المصدر الرسمي بيرجّع 404 في حالتين مختلفتين — (أ) الشات مش موجود
  فعلًا (`'Conversation not found'`)، و(ب) الخدمة فشلت داخليًا (`'Failed to delete
  conversation'`). فممنوع نعتبر 404 نجاحًا تلقائيًا ⇒ بيمر بنفس تسوية الحذف البعيد:
  نتحقق من الوجود (GET) قبل ما نقرر.
- 400/401/403 ⇒ فشل مؤكّد (الحذف البعيد **ما حصلش**) ⇒ مفيش نجاح كاذب، ومسار إعادة محاولة.
- 429/5xx/انقطاع/إعادة توجيه/رد مش متوقع ⇒ نتيجة **مجهولة** ⇒ نفس التسوية (تحقق من الوجود).

قواعد غير قابلة للتفاوض:
- مفيش «نجاح» غير لما OpenHands يأكّد (200) أو التحقق يثبت الغياب بدرجة كافية.
- الغياب لازم يثبت من **أكتر من قراءة** (bounded retry) — القراءة الواحدة مش دليل قاطع.
- مفيش fallback صامت لحذف محلي فقط.
- الملكية بتتفوّض **قبل** النداء (عند المستدعي)، والنتيجة المجهولة تفضل 'uncertain' (تنجو من restart).
"""
from __future__ import annotations

import asyncio
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

# عدد قراءات التحقق من الغياب المطلوبة قبل تأكيد الحذف. `GET /app-conversations?ids=`
# بيقرا من نفس جلسة الكتابة (مفيش replica)، فقراءتين متتاليتين تغطّيان أي رؤية متأخّرة
# طفيفة — وتمنع اعتبار غياب عارض/جزئي دليلًا قاطعًا (bounded: مفيش حلقات مفتوحة).
_ABSENCE_CONFIRMATIONS = 2
_RECHECK_DELAY = 0.1  # ثانية بين القراءات (باك-أوف بسيط ومحدود)


async def _establish_absence(client, conversation_id: str) -> bool | None:
    """يثبت غياب الشات بعيدًا بدرجة كافية. True=غايب (مؤكّد)، False=موجود، None=مش متأكد.

    بيقرا الوجود لحد `_ABSENCE_CONFIRMATIONS` قراءات **متتالية** كلها ترجّع غياب. أي قراءة
    ترجّع «موجود» ⇒ False فورًا (الشات لسه هناك). أي فشل في القراءة ⇒ None (عدم يقين — من
    غير تخمين). العدد محدود ⇒ مفيش نداءات زايدة ولا حلقات مفتوحة.
    """
    for attempt in range(_ABSENCE_CONFIRMATIONS):
        try:
            exists = await client.conversation_exists(conversation_id)
        except ApiError:
            return None  # تعذّر التحقق ⇒ عدم يقين
        if exists:
            return False  # الشات لسه موجود بعيدًا ⇒ الحذف ما حصلش
        if attempt + 1 < _ABSENCE_CONFIRMATIONS:
            await asyncio.sleep(_RECHECK_DELAY)
    return True  # كل القراءات اتّفقت على الغياب ⇒ دليل كافٍ


@dataclass(frozen=True)
class DeletionResult:
    status: str            # STATUS_* فوق
    message: str           # رسالة عربي جاهزة للعرض (مفيش أسرار)
    conversation_id: str
    http_status: int | None = None   # ترميز HTTP لرد الـ Mini App (لو مناسب)
    code: str | None = None          # ترميز خطأ منظّم للواجهة


def _is_definite_failure(status_code: int | None) -> bool:
    """فشل مؤكّد (الحذف البعيد ما حصلش): 4xx **مبهم/قابل لإعادة المحاولة** مستثنى.

    429 (قابل لإعادة المحاولة) و404 (مبهم: غياب أو فشل خدمة داخلي) **مش** فشل مؤكّد —
    لازم يمرّوا بتسوية التحقق من الوجود، مش يُعاملوا كنجاح ولا كفشل نهائي.
    """
    return (
        status_code is not None
        and 400 <= status_code < 500
        and status_code not in (404, 429)
    )


def _finalize(db, conversation_id: str, now: str) -> DeletionResult:
    """يثبّت الحذف المحلي + حالة 'confirmed' (ذرّي) ويرجّع نتيجة نجاح.

    في المسار ده عندنا **دليل إيجابي** إن الشات اتحذف بعيدًا (رد 200 صريح، أو غياب مثبت
    بقراءتين متتاليتين)، فالتثبيت غير مشروط آمن. و`'confirmed'` **حالة نهائية**: كل الـ CAS
    (`revert_remote_deletion_cas`/`clear_witness_cas`) فيه شرط `remote_state != 'confirmed'`،
    فأي محاولة قديمة/أحدث ما تقدرش ترجّع أو تطمس أو تحذف الشاهد المؤكّد ⇒ **لا خطر إحياء**.
    """
    db.delete_conversation(conversation_id, now, remote_confirmed=True)
    return DeletionResult(STATUS_DELETED, DELETED_MESSAGE, conversation_id, http_status=200)


def _restore_snapshot(db, conversation_id: str, attempt_id: str, snapshot) -> None:
    """استرجاع **آمن** لحالة ما قبل المحاولة عبر compare-and-swap على ملكية المحاولة.

    بنستخدم `snapshot` = (pre_state, pre_updated_at, had_witness) المقروءة قبل المحاولة.
    - مفيش شاهد قبلها ⇒ نمسح الصف **بس** لو إحنا لسه المالك (CAS) — منع حذف شاهد أثبته
      عملية أحدث (lost-update).
    - فيه شاهد صريح قبلها (حالة/طابع) ⇒ نرجّعه بالظبط (CAS) — منع طمس حالة أحدث.
    - شاهد قديم (حذف محلي سابق بحالة NULL) ⇒ نرجّع بيانات الحذف البعيد NULL **بس** لو إحنا
      لسه المالك؛ الشاهد نفسه يفضل محفوظ دايمًا (ما بيتحذفش أبدًا في مسار «موجود»).
    الكتابة بتفشل بهدوء (مفيش طمس) لو محاولة أحدث سبقتنا — وده هو المطلوب.
    """
    pre_state, pre_updated_at, had_witness = snapshot
    if pre_state is None:
        if had_witness:
            # شاهد قديم: نرجّع بيانات الحذف البعيد لـ NULL فقط (الشاهد يفضل). CAS.
            db.revert_remote_deletion_cas(conversation_id, attempt_id, None, None)
        else:
            # مفيش شاهد قبل المحاولة ⇒ اشيل الصف **بس** لو لسه ملكنا. CAS.
            db.clear_witness_cas(conversation_id, attempt_id)
    else:
        # حالة صريحة سابقة ⇒ نرجّعها بالظبط. CAS.
        db.revert_remote_deletion_cas(conversation_id, attempt_id, pre_state, pre_updated_at)


async def _reconcile(
    client, db, conversation_id: str, now: str, attempt_id: str, snapshot, pending_ts: str
) -> DeletionResult:
    """تسوية نتيجة الحذف **المبهمة/المجهولة** عبر التحقق من الوجود البعيد.

    - غايب (مؤكّد بقراءات متتالية) ⇒ نثبّت الحذف ('confirmed' + حذف محلي).
    - موجود ⇒ الحذف ما حصلش ⇒ نرجّع الحالة المحلية (CAS) ونبلّغ فشل صريح (مفيش نجاح كاذب).
    - تعذّر التحقق ⇒ 'uncertain' **بس لو إحنا لسه المالك** (CAS) — ينجو من restart ويُسوّى
      لاحقًا، وما يطمسش حالة محاولة أحدث. بنسجّل `pending_ts` (طابع ما قبل المحاولة لو كانت
      إعادة محاولة، وإلا `now`) للحفاظ على الطابع الأصلي. تصنيف الشاهد (قديم/جديد) متين وغير
      زمني فالطابع المسجّل ما بيأثّر فيه (‏TS-1 مُلغى).
    """
    absent = await _establish_absence(client, conversation_id)
    if absent is True:
        return _finalize(db, conversation_id, now)
    if absent is False:
        # اتأكدنا إن الشات لسه موجود ⇒ الحذف ما حصلش ⇒ نرجّع الحالة المحلية.
        _restore_snapshot(db, conversation_id, attempt_id, snapshot)
        return DeletionResult(
            STATUS_FAILED, FAILED_MESSAGE, conversation_id,
            http_status=502, code="remote_delete_failed",
        )
    # تعذّر التحقق ⇒ 'pending' (مش نجاح، ومش فشل مؤكّد) — CAS: بس لو لسه إحنا المالك.
    db.revert_remote_deletion_cas(conversation_id, attempt_id, db.REMOTE_UNCERTAIN, pending_ts)
    return DeletionResult(
        STATUS_PENDING, PENDING_MESSAGE, conversation_id,
        http_status=503, code="remote_delete_pending",
    )


async def delete_conversation_remote(client, db, conversation_id: str) -> DeletionResult:
    """يحذف شات من OpenHands ثم يثبّت الحذف محليًا. يتطلب تفويض ملكية مسبق من المستدعي."""
    now = outbox.now_iso()
    # نقرأ الحالة **والطابع الأصليين** في قراءة واحدة قبل أي كتابة، عشان الاسترجاع بعد الفشل
    # يرجّع نفس القيم بالظبط (مش طابع جديد).
    pre_state, pre_updated_at = db.remote_deletion_metadata(conversation_id)
    # هل كان فيه شاهد حذف محلي **قبل** المحاولة دي؟ (شاهد قديم بحالة NULL من حذف محلي سابق.)
    had_witness = db.is_deleted(conversation_id)
    snapshot = (pre_state, pre_updated_at, had_witness)

    # حذف بعيد مؤكّد سابقًا: نعيد تثبيت الحذف المحلي (idempotent) من غير نداء تاني.
    if pre_state == db.REMOTE_CONFIRMED:
        return _finalize(db, conversation_id, now)

    # نوسم الحذف الجاري **قبل** النداء البعيد (شاهد + 'deleting' + هُوية محاولة فريدة).
    # `attempt_id` هو مفتاح الـ compare-and-swap: أي محاولة/تسوية أحدث بتغيّره، فمحاولتنا
    # ما تقدرش تطمس حالتها بعد كده (منع lost-update). لو الشات مؤكّد الحذف مسبقًا ⇒ None
    # (ما بناخدش ملكية؛ إثبات الحذف نهائي) ⇒ نعيد التثبيت المحلي idempotent.
    attempt_id = db.begin_remote_deletion(conversation_id, now)
    if attempt_id is None:
        return _finalize(db, conversation_id, now)

    try:
        await client.delete_conversation(conversation_id)
    except ApiError as exc:
        code = exc.status_code
        if _is_definite_failure(code):
            # فشل مؤكّد: الحذف البعيد ما حصلش ⇒ نرجّع الحالة المحلية (CAS)، ونبلّغ فشل صريح —
            # مفيش نجاح كاذب ومفيش إخفاء كاذب، ومفيش طمس لمحاولة أحدث ولا لحالة 'confirmed'
            # سبقتنا (الـ CAS في `revert/clear` بيمنع أي كتابة على حالة مؤكّدة ⇒ الحالة نهائية).
            _restore_snapshot(db, conversation_id, attempt_id, snapshot)
            return DeletionResult(
                STATUS_FAILED, FAILED_MESSAGE, conversation_id,
                http_status=code, code="remote_delete_failed",
            )
        # 404 (مبهم) / 429 / 5xx / انقطاع / إعادة توجيه / رد مش متوقع ⇒ نتيجة **مش مؤكّدة**
        # ⇒ تسوية بالتحقق من الوجود قبل أي تأكيد. لو كانت إعادة محاولة على شاهد موجود أصلًا
        # (`pre_updated_at is not None`)، نسجّل 'uncertain' بطابعه الأصلي بدل `now` (F1-R).
        pending_ts = pre_updated_at if pre_updated_at is not None else now
        return await _reconcile(client, db, conversation_id, now, attempt_id, snapshot, pending_ts)

    # OpenHands أكّد (200 success=true) ⇒ نثبّت الحذف المحلي + 'confirmed'.
    return _finalize(db, conversation_id, now)


async def reconcile_pending_deletions(client, db) -> None:
    """تسوية الحذف البعيد المعلّق بعد restart (best-effort، غير قاتل).

    لكل شات حالته 'deleting'/'uncertain' (مع رمز المحاولة المالكة): نتحقق من الوجود بعيدًا.
    - غايب ⇒ نثبّت الحذف (اتحذف فعلًا قبل الانقطاع).
    - موجود ⇒ نرجّعه محليًا بـ CAS على **ملكية** المحاولة: لو الشاهد سبق المحاولة (حذف محلي
      قديم) نسيبه محفوظ ونصفّر بيانات الحذف البعيد بس؛ ولو الشاهد من المحاولة نفسها نشيل
      الصف. كل ده **بس** لو المحاولة المالكة لسه هي نفسها (ما نطمسش محاولة أحدث بدأت بعدنا).
    - تعذّر التحقق ⇒ نسيبه معلّق (مفيش تخمين).
    """
    try:
        pending = db.list_pending_remote_deletions_with_owner()
    except Exception as exc:  # noqa: BLE001 — التسوية ما تمنعش الإقلاع
        log.warning("تعذّر قراءة الحذف البعيد المعلّق (%s)", type(exc).__name__)
        return
    for conversation_id, owner_attempt_id in pending:
        absent = await _establish_absence(client, conversation_id)
        now = outbox.now_iso()
        if absent is True:
            try:
                db.delete_conversation(conversation_id, now, remote_confirmed=True)
                log.info("تسوية: تأكيد حذف بعيد معلّق (%s)", conversation_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("تعذّر تثبيت حذف معلّق (%s)", type(exc).__name__)
        elif absent is False:
            # CAS على ملكية المحاولة: ما نتحرّكش إلا لو المحاولة المالكة لسه زي ما قرأناها.
            try:
                if db.is_legacy_witness(conversation_id):
                    # R1: شاهد سبق المحاولة ⇒ نحافظ على الصف ونصفّر بيانات الحذف البعيد بس.
                    ok = db.revert_remote_deletion_cas(conversation_id, owner_attempt_id, None, None)
                    if ok:
                        log.info("تسوية: شاهد حذف قديم اتّحفظ (الشات لسه موجود) (%s)", conversation_id)
                else:
                    if not db.clear_witness_cas(conversation_id, owner_attempt_id):
                        log.info("تسوية: محاولة أحدث سبقتنا — ما اتحذفش شاهد (%s)", conversation_id)
                    else:
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
