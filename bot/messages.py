"""نصوص عربي + تقسيم الرسايل الطويلة عند حد تيليجرام."""
from __future__ import annotations

import math

TELEGRAM_LIMIT = 4096
MAX_PARTS = 3
# TASK 55 (المرحلة B): حدود معاينة العرض الخفيف + هامش أمان لتنسيق تيليجرام.
PROMPT_PREVIEW = 300
REPLY_PREVIEW = 800
FOOTER_RESERVE = 250  # هامش أمان (مفيش ذيل توجيه بعد إزالة الميزة)
_REPLY_LABEL = "\n\nرد الـ agent:\n"
_NO_REPLY = "لسه مفيش رد."
_REPLY_MIN = 200
_ELLIPSIS = " …"

# حالة نهائية خاصة بفشل بيئة التنفيذ (مش من execution_status؛ مشتقة من sandbox_status).
SANDBOX_ERROR = "sandbox_error"

STATE_LABELS = {
    "running": "شغال",
    "idle": "خامل",
    "paused": "موقوف",
    "waiting_for_confirmation": "مستني تأكيد",
    "finished": "منتهي",
    "error": "خطأ",
    "stuck": "متعلّق",
    "cancelled": "اتلغى",
    "canceled": "اتلغى",
    SANDBOX_ERROR: "خطأ بيئة",
    # OHB2-WP-06 (DEF-009): `get_status({})` بترجّع "unknown" (نص)، فالمفتاح ده لازم
    # يتضاف قبل ما نبدّل مواقع العرض لـ `get_status(conv)` عشان ما تظهرش كلمة إنجليزية.
    "unknown": "غير معروف",
    None: "غير معروف",
}

# OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS: الحالات الدلالية المحلية. لا نعتبر
# `waiting_for_confirmation` نجاحًا، ولا نعتبر `unknown` أو انتهاء مهلة محلية نجاحًا.
TASK_RUNNING = "running"
# حالة المزود وحدها (finished) لا تعني أن التقرير وصل أو اتسلّم.
TASK_PROVIDER_FINISHED = "provider_finished"
TASK_REPORT_PENDING = "report_pending"
TASK_REPORT_AVAILABLE = "report_available"
TASK_REPORT_UNCERTAIN = "report_uncertain"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"
TASK_UNKNOWN = "unknown"
TASK_TIMED_OUT = "timed_out"

TASK_STATE_LABELS = {
    TASK_RUNNING: "شغال",
    TASK_PROVIDER_FINISHED: "المزود أنهى التنفيذ",
    TASK_REPORT_PENDING: "التقرير قيد الانتظار",
    TASK_REPORT_AVAILABLE: "التقرير جاهز (قيد التسليم)",
    TASK_REPORT_UNCERTAIN: "تسليم التقرير غير مؤكد",
    TASK_COMPLETED: "مكتمل",
    TASK_FAILED: "فشل",
    TASK_CANCELLED: "اتلغى",
    TASK_UNKNOWN: "غير معروف",
    TASK_TIMED_OUT: "انتهت المهلة",
}

DONE_STATES = {"finished", "error", "stuck", "waiting_for_confirmation", "cancelled"}
# الحالات النهائية المؤهّلة للإشعار: حالات الانتهاء + خطأ البيئة.
TERMINAL_STATES = DONE_STATES | {SANDBOX_ERROR}

_REPORT_PENDING_STATES = {"pending"}
_REPORT_AVAILABLE_STATES = {"sending"}
_REPORT_UNCERTAIN_STATES = {"uncertain"}
_REPORT_DELIVERED_STATES = {"delivered", "not_required"}


def task_state(status: str | None, report_state: str | None = None) -> str:
    """يحوّل حالة المزود + حالة التقرير إلى حالة دلالية محلية.

    `finished` وحدها لا تعني COMPLETED. التقرير يجب أن يكون مُسلَّمًا (أو غير مطلوب)
    قبل اعتبار سير العمل مكتملًا. الحالات الأخرى:
    - finished + pending ⇒ REPORT_PENDING
    - finished + sending ⇒ REPORT_AVAILABLE
    - finished + uncertain ⇒ REPORT_UNCERTAIN
    - finished + timed_out ⇒ TIMED_OUT
    - finished بدون report_state ⇒ PROVIDER_FINISHED (حقيقة المزود فقط)
    - error/stuck/sandbox_error ⇒ FAILED
    - cancelled/canceled ⇒ CANCELLED
    - running/idle/paused ⇒ RUNNING
    - أي قيمة غير معروفة ⇒ UNKNOWN، وليست COMPLETED.
    """
    if isinstance(status, str):
        status = status.lower()
        if status == "canceled":
            status = "cancelled"
    if status == "finished":
        if report_state == "timed_out":
            return TASK_TIMED_OUT
        if report_state in _REPORT_PENDING_STATES:
            return TASK_REPORT_PENDING
        if report_state in _REPORT_AVAILABLE_STATES:
            return TASK_REPORT_AVAILABLE
        if report_state in _REPORT_UNCERTAIN_STATES:
            return TASK_REPORT_UNCERTAIN
        if report_state in _REPORT_DELIVERED_STATES:
            return TASK_COMPLETED
        return TASK_PROVIDER_FINISHED
    if status in {"error", "stuck", SANDBOX_ERROR}:
        return TASK_FAILED
    if status == "cancelled":
        return TASK_CANCELLED
    if status in {"running", "idle", "paused"}:
        return TASK_RUNNING
    return TASK_UNKNOWN


def task_state_label(state: str | None) -> str:
    if state is None:
        return TASK_STATE_LABELS[TASK_UNKNOWN]
    if not isinstance(state, str):
        return TASK_STATE_LABELS[TASK_UNKNOWN]
    return TASK_STATE_LABELS.get(state, TASK_STATE_LABELS[TASK_UNKNOWN])


def get_status(conversation: dict) -> str:
    """الحالة المعيارية الوحيدة لمحادثة — المصدر الواحد للحقيقة للمراقب والمُبلّغ.

    `execution_status` (بحروف صغيرة)، إلا لو `sandbox_status ∈ {ERROR, MISSING}`
    فالحالة `sandbox_error`. الدالة نقية ومفيهاش أي اعتماد على باقي الوحدات.
    """
    execution = conversation.get("execution_status")
    status = str(execution).lower() if execution is not None else "unknown"
    # OpenHands قد يستخدم التهجئة الأمريكية؛ نوحّدها إلى حالة واحدة.
    if status == "canceled":
        status = "cancelled"
    sandbox = str(conversation.get("sandbox_status") or "").upper()
    if sandbox in {"ERROR", "MISSING"}:
        return SANDBOX_ERROR
    return status


def is_terminal(status: str | None) -> bool:
    """حالة نهائية مؤهّلة للإشعار؟ (تشمل sandbox_error)."""
    return status in TERMINAL_STATES


def state_label(state: str | None) -> str:
    if state is None:
        return STATE_LABELS[None]
    if not isinstance(state, str):
        return "غير معروف"
    return STATE_LABELS.get(state, state or "غير معروف")


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """يقسّم نص خام (مش HTML) لأجزاء، كل جزء طوله ≤ limit.

    حد تيليجرام (4096) بيتقاس "بعد فك كيانات HTML"، أي بطول النص الخام نفسه
    (التهريب بيتحوّل لكيانات بترجع لنفس عدد الحروف بعد الفك). فالتقسيم بيحصل على
    النص الخام قبل التهريب، وبُحافظ على النص كامل: "".join(parts) == text
    (مفيش أي حرف—بما فيه السطور الجديدة—بيتفقد). التقسيم بيفضّل آخر سطر جديد جوه
    الحد، ولو مفيش (نص متصل) بيقصّ عند الحد بالظبط.
    """
    text = text or ""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:]
    return parts


def pr_url(conv: dict) -> str | None:
    """رابط الـ PR لو الشات مرتبط بواحد. pr_number ممكن يكون [1] مش رقم."""
    repo = conv.get("selected_repository")
    numbers = conv.get("pr_number")
    if not repo or not numbers:
        return None
    number = numbers[0] if isinstance(numbers, (list, tuple)) and numbers else numbers
    if number is None:
        return None
    return f"https://github.com/{repo}/pull/{number}"


def format_conversation(conv: dict, reply: str | None) -> str:
    """نص خام (مش HTML). اللي بيعرضه لازم يهرّبه بـ escape_html."""
    title = conv.get("title") or "بدون عنوان"
    repo = conv.get("selected_repository") or "بدون مستودع"
    state = state_label(get_status(conv))
    lines = [title, f"المستودع: {repo}", f"الحالة: {state}"]
    link = pr_url(conv)
    if link:
        lines.append(f"الـ PR: {link}")
    if reply:
        lines.append("")
        lines.append(reply)
    return "\n".join(lines)


def truncate(text: str | None, limit: int) -> tuple[str, bool]:
    """يقصّ نص خام عند حد، ويرجّع (النص، هل اتقص). مسافات بس = نص فاضي."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + " …", True


def format_conversation_view(conv: dict, user_text: str | None, reply: str | None) -> tuple[str, bool]:
    """نص خام (يتهرّب عند العرض). بيرجّع (النص، هل الرد اتقص).

    العرض خفيف (رؤوس + آخر برومت + معاينة الرد) عشان الجهاز يستلم نص صغير بس، والرد
    الكامل بيتبعت عند الطلب من زر «عرض كامل». العنوان الطويل ما يخلّيش الرسالة تعدّي
    حد تيليجرام: بنحجز FOOTER_RESERVE كهامش أمان ونحسب حد الرد من المساحة الباقية.

    انحراف عن البرومت (مقصود، ومغطّى باختبار): البرومت حدّد أرضية 200 للرد دايماً،
    لكن ده بيكسر ضمان ≤4096 لما العنوان يبقى طويل جداً. فبنحصر مساحة الهيدر (العنوان
    + بلوك البرومت) في `TELEGRAM_LIMIT - _REPLY_MIN - FOOTER_RESERVE`؛ العنوان اللي
    أطول من كده بيتقص عشان الأرضية 200 والحد الكلي يفضلوا مضمونين مع بعض.
    """
    title = conv.get("title") or "بدون عنوان"
    repo = conv.get("selected_repository") or "بدون مستودع"
    state = state_label(get_status(conv))
    base = "\n".join([f"المستودع: {repo}", f"الحالة: {state}"])
    link = pr_url(conv)
    if link:
        base += f"\nالـ PR: {link}"
    user_block = ""
    if user_text:
        preview, _ = truncate(user_text, PROMPT_PREVIEW)
        user_block = "\n\nآخر برومت منك:\n" + preview
    reply_block = _REPLY_LABEL
    total_budget = TELEGRAM_LIMIT - FOOTER_RESERVE
    header_budget = total_budget - len(user_block) - len(reply_block) - _REPLY_MIN
    if len(title) + len(base) + 1 > header_budget:
        room = header_budget - len(base) - 1
        cut = title[: max(room - len(_ELLIPSIS), 1)].rstrip() + _ELLIPSIS
        header = cut + "\n" + base
    else:
        header = title + "\n" + base
    head_len = len(header) + len(user_block) + len(reply_block)
    reply_limit = min(REPLY_PREVIEW, total_budget - head_len)
    reply_limit = max(reply_limit, _REPLY_MIN)
    if reply:
        preview, cut = truncate(reply, reply_limit)
        return header + user_block + reply_block + preview, cut
    return header + user_block + reply_block + _NO_REPLY, False


def _finite_number(value):
    """رقم محدود (int/float، مش bool) أو None — نفس تحقّق السيرفر (OHB2-09-A2-03)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def format_cost(metrics: dict | None) -> str:
    """سطر التكلفة والتوكنز من حقل metrics على الشات.

    العقد: الحقل `accumulated_cost` بلا عملة مثبتة ⇒ **مفيش** أي رمز عملة (`$`) ولا
    اسم عملة في المخرَج (OHB2-09-A2-03، نفس قرار OHB2-09-04-R1 على الواجهة). القيم
    غير المحدودة (NaN/±Infinity) والـ bool والقيم غير الرقمية بتتجاهل (مفيش تمثيل كاذب).
    """
    if not isinstance(metrics, dict) or not metrics:
        return "مفيش بيانات تكلفة."
    cost = _finite_number(metrics.get("accumulated_cost"))
    raw_usage = metrics.get("accumulated_token_usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    model = metrics.get("model_name") or usage.get("model") or "غير معروف"
    lines = [f"الموديل: {model}"]
    if cost is not None:
        # F1 (BATCH-C): عدد صحيح ضخم (أكبر من مدى الـ double) بيكسر float() بـ OverflowError.
        # `_finite_number` بيقبله (int محدود) لكن التحويل ممكن يفشل ⇒ نرجع للتمثيل النصي
        # الدقيق للعدد الصحيح بدل ما نرمي استثناء جوه معالج الـ callback.
        try:
            lines.append(f"التكلفة التراكمية: {float(cost):.4f}")
        except (OverflowError, ValueError):
            lines.append(f"التكلفة التراكمية: {cost}")
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if prompt is not None or completion is not None:
        lines.append(f"توكنز الإدخال: {prompt or 0}")
        lines.append(f"توكنز الإخراج: {completion or 0}")
    return "\n".join(lines)


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
