"""نصوص عربي + تقسيم الرسايل الطويلة عند حد تيليجرام."""
from __future__ import annotations

TELEGRAM_LIMIT = 4096
MAX_PARTS = 3
# TASK 55 (المرحلة B): حدود معاينة العرض الخفيف + مساحة محجوزة لذيل التوجيه.
PROMPT_PREVIEW = 300
REPLY_PREVIEW = 800
FOOTER_RESERVE = 250  # مساحة لذيل التوجيه اللي بيتضاف في handlers
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
    SANDBOX_ERROR: "خطأ بيئة",
    None: "غير معروف",
}

DONE_STATES = {"finished", "error", "stuck", "waiting_for_confirmation"}
# الحالات النهائية المؤهّلة للإشعار: حالات الانتهاء + خطأ البيئة.
TERMINAL_STATES = DONE_STATES | {SANDBOX_ERROR}


def get_status(conversation: dict) -> str:
    """الحالة المعيارية الوحيدة لمحادثة — المصدر الواحد للحقيقة للمراقب والمُبلّغ.

    `execution_status` (بحروف صغيرة)، إلا لو `sandbox_status ∈ {ERROR, MISSING}`
    فالحالة `sandbox_error`. الدالة نقية ومفيهاش أي اعتماد على باقي الوحدات.
    """
    execution = conversation.get("execution_status")
    status = str(execution).lower() if execution is not None else "unknown"
    sandbox = str(conversation.get("sandbox_status") or "").upper()
    if sandbox in {"ERROR", "MISSING"}:
        return SANDBOX_ERROR
    return status


def is_terminal(status: str | None) -> bool:
    """حالة نهائية مؤهّلة للإشعار؟ (تشمل sandbox_error)."""
    return status in TERMINAL_STATES


def state_label(state: str | None) -> str:
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
    state = state_label(conv.get("execution_status"))
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
    حد تيليجرام مع الذيل: بنحجز FOOTER_RESERVE ونحسب حد الرد من المساحة الباقية.

    انحراف عن البرومت (مقصود، ومغطّى باختبار): البرومت حدّد أرضية 200 للرد دايماً،
    لكن ده بيكسر ضمان ≤4096 لما العنوان يبقى طويل جداً. فبنحصر مساحة الهيدر (العنوان
    + بلوك البرومت) في `TELEGRAM_LIMIT - _REPLY_MIN - FOOTER_RESERVE`؛ العنوان اللي
    أطول من كده بيتقص عشان الأرضية 200 والحد الكلي يفضلوا مضمونين مع بعض.
    """
    title = conv.get("title") or "بدون عنوان"
    repo = conv.get("selected_repository") or "بدون مستودع"
    state = state_label(conv.get("execution_status"))
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


def format_cost(metrics: dict | None) -> str:
    """سطر التكلفة والتوكنز من حقل metrics على الشات."""
    if not metrics:
        return "مفيش بيانات تكلفة."
    cost = metrics.get("accumulated_cost")
    usage = metrics.get("accumulated_token_usage") or {}
    model = metrics.get("model_name") or usage.get("model") or "غير معروف"
    lines = [f"الموديل: {model}"]
    if cost is not None:
        try:
            cost = f"{float(cost):.4f}"
        except (TypeError, ValueError):
            pass
        lines.append(f"التكلفة التراكمية: ${cost}")
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
