"""أزرار inline للبوت."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .messages import state_label

CALLBACK_DATA_LIMIT = 64  # حد تيليجرام بالبايت


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    """زر بـ callback_data متحقَّق منه: أي قيمة أطول من 64 بايت ترفع خطأ بدل ما تتكسر عند الإرسال."""
    if len(callback_data.encode("utf-8")) > CALLBACK_DATA_LIMIT:
        raise ValueError("callback_data أطول من 64 بايت")
    return InlineKeyboardButton(text, callback_data=callback_data)

BACK = "رجوع"
REPLY = "رد"
REFRESH = "تحديث"
NEW_CHAT = "شات جديد"
MY_CHATS = "شاتاتي"
MORE = "المزيد"
STATUS = "الحالة"
FILES = "الملفات"
COST = "التكلفة"
EXPORT = "تصدير"
WATCHES = "متابعاتي"
WATCH = "تابع"
UNWATCH = "إلغاء"
CANCEL_ROUTE = "إلغاء التوجيه"


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _btn(MY_CHATS, callback_data="list:0"),
                _btn(NEW_CHAT, callback_data="newchat"),
            ],
            [_btn(WATCHES, callback_data="watched:0")],
        ]
    )


def watches_menu(items: list, page: int, has_more: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for w in items:
        title = (w.title or "بدون عنوان")[:32]
        label = f"{title} — {state_label(w.last_state)}"
        rows.append(
            [
                _btn(label, callback_data=f"open:{w.conversation_id}"),
                _btn(UNWATCH, callback_data=f"unwatch:{w.conversation_id}"),
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("السابق", callback_data=f"watched:{page - 1}"))
    if has_more:
        nav.append(_btn(MORE, callback_data=f"watched:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BACK, callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def conversations_menu(items: list[dict], page: int, has_more: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for conv in items:
        title = (conv.get("title") or "بدون عنوان")[:40]
        label = f"{title} — {state_label(conv.get('execution_status'))}"
        rows.append([_btn(label, callback_data=f"open:{conv['id']}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("السابق", callback_data=f"list:{page - 1}"))
    if has_more:
        nav.append(_btn(MORE, callback_data=f"list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BACK, callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def conversation_actions(conversation_id: str, watched: bool = False) -> InlineKeyboardMarkup:
    toggle = (
        _btn("إلغاء المتابعة", callback_data=f"unwatch:{conversation_id}")
        if watched
        else _btn(WATCH, callback_data=f"watch:{conversation_id}")
    )
    return InlineKeyboardMarkup(
        [
            [
                _btn(REPLY, callback_data=f"reply:{conversation_id}"),
                _btn(REFRESH, callback_data=f"open:{conversation_id}"),
            ],
            [
                _btn(STATUS, callback_data=f"status:{conversation_id}"),
                _btn(FILES, callback_data=f"files:{conversation_id}:0"),
                _btn(COST, callback_data=f"cost:{conversation_id}"),
            ],
            [_btn(EXPORT, callback_data=f"export:{conversation_id}"), toggle],
            [
                _btn(BACK, callback_data="list:0"),
                _btn(CANCEL_ROUTE, callback_data="cancelroute"),
            ],
        ]
    )


def files_menu(conversation_id: str, files: list[str], start: int, page: int, has_more: bool) -> InlineKeyboardMarkup:
    # callback data بحد 64 بايت، فبنستخدم رقم الملف مش مساره الكامل.
    rows: list[list[InlineKeyboardButton]] = []
    for offset, name in enumerate(files):
        rows.append([_btn(name[:60], callback_data=f"file:{conversation_id}:{start + offset}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("السابق", callback_data=f"files:{conversation_id}:{page - 1}"))
    if has_more:
        nav.append(_btn(MORE, callback_data=f"files:{conversation_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(BACK, callback_data=f"open:{conversation_id}")])
    return InlineKeyboardMarkup(rows)


def repositories_menu(items: list[dict], page: int, has_more: bool, gen: int, start: int = 0) -> InlineKeyboardMarkup:
    """أزرار المستودعات بدون أي نص حر في callback_data.

    الأزرار بتحمل رقم نسخة القايمة (gen) وفهرس المستودع فقط؛ الاسم الكامل والبحث
    محفوظين في حالة السيرفر. زر قديم (gen مختلف) بيتتجاهل بأمان.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for offset, repo in enumerate(items):
        name = repo.get("full_name") or "بدون اسم"
        rows.append([_btn(name, callback_data=f"pickrepo:{gen}:{start + offset}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("السابق", callback_data=f"repos:{gen}:{page - 1}"))
    if has_more:
        nav.append(_btn(MORE, callback_data=f"repos:{gen}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn("بحث", callback_data="reposearch")])
    rows.append([_btn(BACK, callback_data="menu")])
    return InlineKeyboardMarkup(rows)
