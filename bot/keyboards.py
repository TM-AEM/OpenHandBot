"""أزرار inline للبوت."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .messages import state_label

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


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(MY_CHATS, callback_data="list:0"), InlineKeyboardButton(NEW_CHAT, callback_data="newchat")]]
    )


def conversations_menu(items: list[dict], page: int, has_more: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for conv in items:
        title = (conv.get("title") or "بدون عنوان")[:40]
        label = f"{title} — {state_label(conv.get('execution_status'))}"
        rows.append([InlineKeyboardButton(label, callback_data=f"open:{conv['id']}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("السابق", callback_data=f"list:{page - 1}"))
    if has_more:
        nav.append(InlineKeyboardButton(MORE, callback_data=f"list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(BACK, callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def conversation_actions(conversation_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(REPLY, callback_data=f"reply:{conversation_id}"),
                InlineKeyboardButton(REFRESH, callback_data=f"open:{conversation_id}"),
            ],
            [
                InlineKeyboardButton(STATUS, callback_data=f"status:{conversation_id}"),
                InlineKeyboardButton(FILES, callback_data=f"files:{conversation_id}:0"),
                InlineKeyboardButton(COST, callback_data=f"cost:{conversation_id}"),
            ],
            [InlineKeyboardButton(EXPORT, callback_data=f"export:{conversation_id}")],
            [InlineKeyboardButton(BACK, callback_data="list:0")],
        ]
    )


def files_menu(conversation_id: str, files: list[str], start: int, page: int, has_more: bool) -> InlineKeyboardMarkup:
    # callback data بحد 64 بايت، فبنستخدم رقم الملف مش مساره الكامل.
    rows: list[list[InlineKeyboardButton]] = []
    for offset, name in enumerate(files):
        rows.append([InlineKeyboardButton(name[:60], callback_data=f"file:{conversation_id}:{start + offset}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("السابق", callback_data=f"files:{conversation_id}:{page - 1}"))
    if has_more:
        nav.append(InlineKeyboardButton(MORE, callback_data=f"files:{conversation_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(BACK, callback_data=f"open:{conversation_id}")])
    return InlineKeyboardMarkup(rows)


def repositories_menu(items: list[dict], page: int, query: str, has_more: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for repo in items:
        name = repo.get("full_name") or "بدون اسم"
        rows.append([InlineKeyboardButton(name, callback_data=f"pickrepo:{name}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("السابق", callback_data=f"repos:{page - 1}:{query}"))
    if has_more:
        nav.append(InlineKeyboardButton(MORE, callback_data=f"repos:{page + 1}:{query}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("بحث", callback_data="reposearch")])
    rows.append([InlineKeyboardButton(BACK, callback_data="menu")])
    return InlineKeyboardMarkup(rows)
