"""نصوص عربي + تقسيم الرسايل الطويلة عند حد تيليجرام."""
from __future__ import annotations

TELEGRAM_LIMIT = 4096
MAX_PARTS = 3

STATE_LABELS = {
    "running": "شغال",
    "idle": "خامل",
    "paused": "موقوف",
    "waiting_for_confirmation": "مستني تأكيد",
    "finished": "منتهي",
    "error": "خطأ",
    "stuck": "متعلّق",
    None: "غير معروف",
}

DONE_STATES = {"finished", "error", "stuck", "waiting_for_confirmation"}


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
