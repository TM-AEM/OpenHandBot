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
        text = text[cut:].lstrip("\n")
    return parts


def format_conversation(conv: dict, reply: str | None) -> str:
    """نص خام (مش HTML). اللي بيعرضه لازم يهرّبه بـ escape_html."""
    title = conv.get("title") or "بدون عنوان"
    repo = conv.get("selected_repository") or "بدون مستودع"
    state = state_label(conv.get("execution_status"))
    lines = [title, f"المستودع: {repo}", f"الحالة: {state}"]
    if reply:
        lines.append("")
        lines.append(reply)
    return "\n".join(lines)


def escape_html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
