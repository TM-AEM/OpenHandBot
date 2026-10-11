"""أوامر تيليجرام وأزرارها. كل الرسايل عربي، والمستخدم المالك بس يترد عليه."""
from __future__ import annotations

import asyncio
import io
import logging

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import keyboards as kb
from .errors import ApiError
from .messages import escape_html, format_conversation, format_cost, pr_url, state_label
from .sender import send_long

log = logging.getLogger(__name__)

PAGE_SIZE = 10
REPOS_PAGE_SIZE = 8
FILES_PAGE_SIZE = 10


def _allowed(update: Update, config) -> bool:
    user = update.effective_user
    return bool(user and config.is_allowed(user.id))


class _MessageAdapter:
    """يخلي Message يبان زي CallbackQuery بالنسبة لـ edit_message_text."""

    def __init__(self, message) -> None:
        self._message = message

    async def edit_message_text(self, text: str, **kwargs) -> None:
        await self._message.edit_text(text, **kwargs)


async def _safe_edit(query, text: str, **kwargs) -> bool:
    """يرجّع True لو اتعدّلت الرسالة، وFalse لو مفيش تغيير (زر تحديث)."""
    try:
        await query.edit_message_text(text, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        if "not modified" not in str(exc).lower():
            raise
        return False


async def _edit_or_send(query, text: str, chat_id: int, bot, **kwargs) -> None:
    """يعدّل الرسالة الحالية؛ ولو طويلة عليها يبعتها مقسّمة من جديد."""
    try:
        await query.edit_message_text(escape_html(text), parse_mode=ParseMode.HTML, **kwargs)
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "not modified" in message:
            return
        if "too long" in message:
            await send_long(chat_id, text, bot)
            return
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
    page = int(q.data.split(":", 1)[1])
    client = context.bot_data["client"]
    # نجيب لحد 100 شات مرة واحدة ونرتّبهم إحنا، عشان الترتيب الخام من الـ API
    # مش مضمون وبيكسر الترقيم لو رتّبنا كل صفحة لوحدها.
    try:
        result = await client.search_conversations(limit=100)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    items = result["items"]
    if not items:
        await _safe_edit(q, "ما فيهاش شاتات.", reply_markup=kb.main_menu())
        return
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        page, start = 0, 0
        chunk = items[:PAGE_SIZE]
    has_more = len(items) > start + PAGE_SIZE
    await _safe_edit(
        q,
        f"آخر الشاتات (صفحة {page + 1}):",
        reply_markup=kb.conversations_menu(chunk, page, has_more),
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
    watched = context.bot_data["db"].is_watched(conversation_id)
    text = format_conversation(conv, reply)
    markup = kb.conversation_actions(conversation_id, watched)
    await _edit_or_send(q, text, q.message.chat_id, context.bot, reply_markup=markup)


async def list_watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    page = int(q.data.split(":", 1)[1])
    items = context.bot_data["db"].list_watched()
    if not items:
        await _safe_edit(q, "مفيش شاتات متابَعة.", reply_markup=kb.main_menu())
        return
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        page, start = 0, 0
        chunk = items[:PAGE_SIZE]
    has_more = len(items) > start + PAGE_SIZE
    await _safe_edit(
        q,
        f"متابعاتي (صفحة {page + 1}) — {len(items)} شات:",
        reply_markup=kb.watches_menu(chunk, page, has_more),
    )


async def watch_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    try:
        conv = await _conversation(client, conversation_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    if not conv:
        await _safe_edit(q, "الشات مش موجود.")
        return
    db.add_watched(conversation_id, conv.get("title", ""), q.message.chat_id)
    db.set_last_state(conversation_id, conv.get("execution_status") or "")
    await _safe_edit(
        q, "تمام، الشات اتضاف للمتابعة ✅", reply_markup=kb.conversation_actions(conversation_id, True)
    )


async def unwatch_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    context.bot_data["db"].remove_watched(conversation_id)
    await _safe_edit(q, "تمام، اتشال من المتابعة.")


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    try:
        conv = await _conversation(client, conversation_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    if not conv:
        await _safe_edit(q, "الشات مش موجود.")
        return
    lines = [
        f"العنوان: {conv.get('title') or 'بدون عنوان'}",
        f"الحالة: {state_label(conv.get('execution_status'))}",
        f"الـ sandbox: {conv.get('sandbox_status') or 'غير معروف'}",
    ]
    link = pr_url(conv)
    if link:
        lines.append(f"الـ PR: {link}")
    await _edit_or_send(
        q, "\n".join(lines), q.message.chat_id, context.bot,
        reply_markup=kb.conversation_actions(conversation_id),
    )


async def show_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    try:
        conv = await _conversation(client, conversation_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    await _edit_or_send(
        q, format_cost(conv.get("metrics")), q.message.chat_id, context.bot,
        reply_markup=kb.conversation_actions(conversation_id),
    )


async def export_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    try:
        data = await client.export_conversation(conversation_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    buffer = io.BytesIO(data)
    await context.bot.send_document(
        chat_id=q.message.chat_id,
        document=InputFile(buffer, filename=f"conversation-{conversation_id[:8]}.zip"),
    )


async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    _, conversation_id, page_raw = q.data.split(":", 2)
    page = int(page_raw)
    client = context.bot_data["client"]
    try:
        files = await client.list_files(conversation_id)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    if not files:
        await _safe_edit(q, "ما فيهاش ملفات.", reply_markup=kb.conversation_actions(conversation_id))
        return
    # نخزّن القايمة عشان الـ callback data (حد 64 بايت) ما يشيلش المسار الكامل.
    context.bot_data.setdefault("file_cache", {})[conversation_id] = files
    start = page * FILES_PAGE_SIZE
    chunk = files[start : start + FILES_PAGE_SIZE]
    has_more = len(files) > start + FILES_PAGE_SIZE
    await _safe_edit(
        q,
        f"ملفات الشات (صفحة {page + 1}):",
        reply_markup=kb.files_menu(conversation_id, chunk, start, page, has_more),
    )


async def show_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    _, conversation_id, index_raw = q.data.split(":", 2)
    files = context.bot_data.get("file_cache", {}).get(conversation_id) or []
    index = int(index_raw)
    if index >= len(files):
        await _safe_edit(q, "الملف مش موجود، افتح قايمة الملفات تاني.")
        return
    path = files[index]
    client = context.bot_data["client"]
    try:
        content = await client.read_file(conversation_id, path)
    except ApiError as exc:
        await _safe_edit(q, str(exc))
        return
    name = path.rsplit("/", 1)[-1] or "file.txt"
    buffer = io.BytesIO(content.encode("utf-8"))
    await context.bot.send_document(
        chat_id=q.message.chat_id, document=InputFile(buffer, filename=name)
    )


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
        db.add_watched(conversation_id, conv.get("title", ""), chat_id)
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
        db.add_watched(conversation_id, repo or "", chat_id)
        db.set_last_state(conversation_id, "running")
    except ApiError as exc:
        await bot.send_message(chat_id=chat_id, text=f"فشل بدء الشات: {exc}")
