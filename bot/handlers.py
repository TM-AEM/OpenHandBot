"""أوامر تيليجرام وأزرارها. كل الرسايل عربي، والمستخدم المالك بس يترد عليه."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import keyboards as kb
from .errors import ApiError
from .messages import format_conversation
from .sender import send_long

log = logging.getLogger(__name__)

PAGE_SIZE = 10
REPOS_PAGE_SIZE = 8


def _allowed(update: Update, config) -> bool:
    user = update.effective_user
    return bool(user and config.is_allowed(user.id))


class _MessageAdapter:
    """يخلي Message يبان زي CallbackQuery بالنسبة لـ edit_message_text."""

    def __init__(self, message) -> None:
        self._message = message

    async def edit_message_text(self, text: str, **kwargs) -> None:
        await self._message.edit_text(text, **kwargs)


async def _safe_edit(query, text: str, **kwargs) -> None:
    """يرجّع True لو اتعدّلت الرسالة، وFalse لو مفيش تغيير."""
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception as exc:  # noqa: BLE001 - "Message is not modified" شائع مع زر تحديث
        if "not modified" not in str(exc).lower():
            raise


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg = context.bot_data["config"]
    if not _allowed(update, cfg):
        log.info("تجاهل رسالة من مستخدم غير مسموح: %s", update.effective_user and update.effective_user.id)
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    await update.message.reply_text(
        "أهلاً 👋\nأنا بوت تحكمك في OpenHands Cloud.\n"
        "اختار من الأزرار تحت، أو ابعت برومت بعد ما تعمل رد على شات.",
        reply_markup=kb.main_menu(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    await q.edit_message_text("أهلاً 👋 اختار من الأزرار:", reply_markup=kb.main_menu())


async def list_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    cursor = q.data.split(":", 1)[1]
    page_id = None if cursor == "first" else cursor
    client = context.bot_data["client"]
    page = 0 if page_id is None else 1
    try:
        result = await client.search_conversations(limit=PAGE_SIZE + 1, page_id=page_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    items = result["items"]
    has_more = len(items) > PAGE_SIZE
    items = items[:PAGE_SIZE]
    if not items:
        await _safe_edit(q, "ما فيهاش شاتات.", reply_markup=kb.main_menu())
        return
    await _safe_edit(
        q,
        f"آخر الشاتات (صفحة {page + 1}):",
        reply_markup=kb.conversations_menu(items, result.get("next_page_id"), has_more),
    )


async def open_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    try:
        convs = await client.get_conversations([conversation_id])
        if not convs:
            await q.edit_message_text("الشات مش موجود.")
            return
        conv = convs[0]
        reply = await client.get_last_reply(conversation_id)
    except ApiError as exc:
        await q.edit_message_text(str(exc))
        return
    text = format_conversation(conv, reply)
    try:
        await q.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb.conversation_actions(conversation_id)
        )
    except Exception:  # noqa: BLE001 - التقسيم للرسايل الطويلة
        await send_long(q.message.chat_id, text, context.bot)


async def reply_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    db = context.bot_data["db"]
    db.set_awaiting(update.effective_user.id, conversation_id, "reply")
    await _safe_edit(
        q,
        "ابعت البرومت اللي عايز تبعته للشات ده دلوقتي.",
        reply_markup=kb.conversation_actions(conversation_id),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    telegram_id = update.effective_user.id
    pending, kind = db.get_awaiting(telegram_id)
    if kind == "reply" and pending:
        db.clear_awaiting(telegram_id)
        await _send_prompt(update, context, pending, update.message.text)
    elif kind == "newchat":
        db.clear_awaiting(telegram_id)
        await _start_new_chat(update, context, pending, update.message.text)
    elif kind == "reposearch":
        db.clear_awaiting(telegram_id)
        query = update.message.text.strip()
        sent = await update.message.reply_text("اختار مستودع للشات الجديد:\nبحث: " + query)
        await _show_repos(_MessageAdapter(sent), context, page=0, query=query)
    else:
        await update.message.reply_text("ابعت /start للقائمة، أو اختار شات ورد عليه.")


async def _send_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, conversation_id: str, text: str) -> None:
    """يرد 'وصل' فوراً (أقل من ثانية) والإرسال الفعلي في الخلفية."""
    if not text.strip():
        return
    await update.message.reply_text("وصل ✅")
    asyncio.create_task(
        _deliver_prompt(context, update.effective_chat.id, conversation_id, text)
    )


async def _deliver_prompt(context: ContextTypes.DEFAULT_TYPE, chat_id: int, conversation_id: str, text: str) -> None:
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    bot = context.bot
    try:
        conv = await _conversation(client, conversation_id)
        sandbox_id = conv.get("sandbox_id")
        status = str(conv.get("sandbox_status", "")).upper()

        if status != "RUNNING" and sandbox_id:
            await client.resume_sandbox(sandbox_id)
            status = await _wait_running(client, conversation_id, interval=3.0, timeout=120.0)

        if status != "RUNNING":
            await bot.send_message(chat_id=chat_id, text="الـ sandbox مش قادر يشتغل، جرّب تفتح الشات من الموقع.")
            return

        await client.send_message(conversation_id, text)
        await bot.send_message(chat_id=chat_id, text="اتبعت ✅ الشات اتضاف للمتابعة.")
        db.add_watched(conversation_id, conv.get("title", ""))
        db.set_last_state(conversation_id, "running")
    except ApiError as exc:
        await bot.send_message(chat_id=chat_id, text=f"فشل الإرسال: {exc}")


async def _conversation(client, conversation_id: str) -> dict:
    convs = await client.get_conversations([conversation_id])
    return convs[0] if convs else {}


async def _wait_running(client, conversation_id: str, interval: float, timeout: float) -> str:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(interval)
        conv = await _conversation(client, conversation_id)
        status = str(conv.get("sandbox_status", "")).upper()
        if status == "RUNNING":
            return status
    return "UNKNOWN"


async def start_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    await _show_repos(q, context, page=0, query="")


async def repos_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    _, page, query = (q.data.split(":", 2) + [""])[:3]
    await _show_repos(q, context, page=int(page), query=query)


async def repo_search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].set_awaiting(update.effective_user.id, "", "reposearch")
    await _safe_edit(q, "ابعت كلمة للبحث في المستودعات.")


async def _show_repos(q, context: ContextTypes.DEFAULT_TYPE, page: int, query: str) -> None:
    client = context.bot_data["client"]
    try:
        repos = await client.search_repositories(query=query)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    start = page * REPOS_PAGE_SIZE
    chunk = repos[start : start + REPOS_PAGE_SIZE]
    if not chunk:
        await _safe_edit(q, "ما لقيتش مستودعات.", reply_markup=kb.main_menu())
        return
    has_more = len(repos) > start + REPOS_PAGE_SIZE
    title = "اختار مستودع للشات الجديد:" + (f"\nبحث: {query}" if query else "")
    await _safe_edit(q, title, reply_markup=kb.repositories_menu(chunk, page, query, has_more))


async def pick_repo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    repo = q.data.split(":", 1)[1]
    context.bot_data["db"].set_awaiting(update.effective_user.id, repo, "newchat")
    await _safe_edit(q, f"المستودع: {repo}\nابعت البرومت اللي عايز تبدأ بيه الشات.")


async def _start_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, repo: str | None, text: str) -> None:
    if not text.strip():
        return
    await update.message.reply_text("وصل ✅ جاري بدء شات جديد.")
    asyncio.create_task(_create_chat(context, update.effective_chat.id, repo, text))


async def _create_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, repo: str | None, text: str) -> None:
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    bot = context.bot
    try:
        task_id = await client.start_conversation(text, repo)
        conversation_id = await client.wait_for_start(task_id)
        await bot.send_message(
            chat_id=chat_id,
            text=f"بدأ الشات ✅\n{context.bot_data['config'].openhands_base_url}/canvas/conversations/{conversation_id}",
        )
        db.add_watched(conversation_id, repo or "")
        db.set_last_state(conversation_id, "running")
    except ApiError as exc:
        await bot.send_message(chat_id=chat_id, text=f"فشل بدء الشات: {exc}")
