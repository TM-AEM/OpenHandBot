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
            [InlineKeyboardButton(BACK, callback_data="list:0")],
        ]
    )


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
