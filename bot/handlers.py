"""أوامر تيليجرام وأزرارها. كل الرسايل عربي، والمستخدم المالك بس يترد عليه."""
from __future__ import annotations

import io
import logging

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import keyboards as kb
from . import outbox
from .errors import ApiError, error_text
from .file_cache import FileCache
from .messages import escape_html, format_conversation, format_cost, pr_url, state_label
from .sender import send_long

log = logging.getLogger(__name__)

PAGE_SIZE = 10
REPOS_PAGE_SIZE = 8
FILES_PAGE_SIZE = 10


def _allowed(update: Update, config) -> bool:
    """مستخدم مسموح *و* في محادثة خاصة. صلاحية المستخدم ما تعنيش صلاحية أي جروب."""
    user = update.effective_user
    if not (user and config.is_allowed(user.id)):
        return False
    chat = getattr(update, "effective_chat", None)
    return chat is not None and getattr(chat, "type", None) == "private"


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
    """يعدّل الرسالة الحالية؛ ولو طويلة عليها يبعتها مقسّمة من جديد.

    بيرجّع True لو اتعرض العرض فعلاً (اتعدّلت الرسالة أو اتبعتت من جديد)، وFalse لو
    فشل العرض (خطأ تيليجرام زي رسالة قديمة/مش قابلة للتعديل). الفشل بيتسجّل بنوعه بس
    (من غير نص الاستثناء، ممكن يحتوي أسرار) عشان ما يتخفيش — بس ما يوقّفش معالج الـ
    callback. اللي بينده لازم ياخد باله من القيمة الراجعة قبل أي تغيير في الحالة.
    """
    try:
        await query.edit_message_text(escape_html(text), parse_mode=ParseMode.HTML, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "not modified" in message:
            return True  # العرض نفسه موجود بالفعل — مش فشل
        if "too long" in message:
            await send_long(chat_id, text, bot)
            return True
        log.warning("فشل عرض الشات (%s)", type(exc).__name__)
        return False


def _file_cache(context: ContextTypes.DEFAULT_TYPE) -> FileCache:
    """ذاكرة الملفات المؤقتة المحدودة (LRU) من bot_data (بتتعمل مرة واحدة)."""
    return context.bot_data.setdefault("file_cache", FileCache())


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg = context.bot_data["config"]
    if not _allowed(update, cfg):
        chat = getattr(update, "effective_chat", None)
        log.info(
            "تجاهل تحديث غير مسموح (مستخدم=%s، نوع الشات=%s)",
            update.effective_user and update.effective_user.id,
            getattr(chat, "type", None),
        )
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await update.message.reply_text(
        "أهلاً 👋\nأنا بوت تحكمك في OpenHands Cloud.\n"
        "اختار من الأزرار تحت، أو افتح شات وابعتله برومت.",
        reply_markup=kb.main_menu(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    await q.edit_message_text("أهلاً 👋 اختار من الأزرار:", reply_markup=kb.main_menu())


async def list_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    page = int(q.data.split(":", 1)[1])
    client = context.bot_data["client"]
    # نجيب لحد 100 شات مرة واحدة ونرتّبهم إحنا، عشان الترتيب الخام من الـ API
    # مش مضمون وبيكسر الترقيم لو رتّبنا كل صفحة لوحدها.
    try:
        result = await client.search_conversations(limit=100)
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
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
            # رسالة "مش موجود" بتتعدّل بالمسار المتسامح: فشل تعديل متوقّع (رسالة قديمة/
            # مش قابلة للتعديل) ما يوقّفش الـ callback، وما بيفعّلش أي توجيه.
            await _edit_or_send(q, "الشات مش موجود.", q.message.chat_id, context.bot)
            return
        conv = convs[0]
        reply = await client.get_last_reply(conversation_id)
    except ApiError as exc:
        # نفس المسار المتسامح لرسالة الخطأ: مفيش توجيه جديد ولا انهيار في الـ callback.
        await _edit_or_send(q, error_text(exc), q.message.chat_id, context.bot)
        return
    db = context.bot_data["db"]
    watched = db.is_watched(conversation_id)
    text = format_conversation(conv, reply) + "\n\n✉️ رسايلك الجاية هتتبعت للشات ده (10 دقايق من آخر نشاط). للإلغاء: زر إلغاء التوجيه أو /cancel."
    markup = kb.conversation_actions(conversation_id, watched)
    # القرار 1: بعد فتح الشات، رسايلك الجاية بتتوجّه له 10 دقايق من آخر نشاط (مع زر إلغاء).
    # بنفعّل التوجيه بس بعد ما العرض يظهر فعلاً، عشان فشل العرض ما يسبش توجيه مفعّل من غير
    # ما تشوف الشات (وما نلمسش أي توجيه قائم لو الفتح فشل).
    if await _edit_or_send(q, text, q.message.chat_id, context.bot, reply_markup=markup):
        db.set_awaiting(update.effective_user.id, conversation_id, "route", title=conv.get("title") or "")


async def list_watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
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
        await _safe_edit(q, error_text(exc))
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
        await _safe_edit(q, error_text(exc))
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
        await _safe_edit(q, error_text(exc))
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
        await _safe_edit(q, error_text(exc))
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
    parts = q.data.split(":")
    if len(parts) < 2:
        await _safe_edit(q, _FILES_EXPIRED)
        return
    conversation_id = parts[1]
    # أزرار قديمة (بدون gen) أو صفحة مش رقم ⇒ نتجاهلها بأمان برسالة ودّية.
    try:
        page = int(parts[-1])
    except ValueError:
        await _safe_edit(q, _FILES_EXPIRED)
        return
    client = context.bot_data["client"]
    try:
        files = await client.list_files(conversation_id)
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
        return
    if not files:
        await _safe_edit(q, "ما فيهاش ملفات.", reply_markup=kb.conversation_actions(conversation_id))
        return
    # نخزّن القايمة عشان الـ callback data (حد 64 بايت) ما يشيلش المسار الكامل.
    # ذاكرة مؤقتة محدودة (LRU) مع نسخة لكل شات: أي زر قديم (نسخة أقدم/اتشال) بيرجّع «مش موجود».
    gen = _file_cache(context).put(conversation_id, files)
    start = page * FILES_PAGE_SIZE
    chunk = files[start : start + FILES_PAGE_SIZE]
    has_more = len(files) > start + FILES_PAGE_SIZE
    await _safe_edit(
        q,
        f"ملفات الشات (صفحة {page + 1}):",
        reply_markup=kb.files_menu(conversation_id, chunk, start, page, has_more, gen),
    )


async def show_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    try:
        _, conversation_id, gen_raw, index_raw = q.data.split(":", 3)
        gen, index = int(gen_raw), int(index_raw)
    except ValueError:
        await _safe_edit(q, _FILES_EXPIRED)
        return
    # النسخة والاتشاف لازم يطابقوا الحالة الحالية للذاكرة: أي زر قديم (نسخة أقدم)، أو
    # ملف اتشال/اتغير، أو شات مش موجود ⇒ «مش موجود» من غير أي كشف لمحتوى الشات.
    found = _file_cache(context).get(conversation_id, gen)
    if found is None:
        await _safe_edit(q, _FILE_MISSING)
        return
    files, _ = found
    if index >= len(files):
        await _safe_edit(q, _FILE_MISSING)
        return
    path = files[index]
    client = context.bot_data["client"]
    try:
        content = await client.read_file(conversation_id, path)
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
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
    # U04: القراءة والاستهلاك (أو تجديد المهلة لو route) معاملة واحدة ذرّية، فرسالتين
    # متزامنتين ما يقدروش يستهلكوا نفس حالة الانتظار ولا يتوجّهوا لشات غلط.
    pending, kind, title = db.take_awaiting(telegram_id)
    if kind in ("reply", "route") and pending:
        await _send_prompt(update, context, pending, update.message.text, title if kind == "route" else None)
    elif kind == "newchat":
        await _start_new_chat(update, context, pending, update.message.text)
    elif kind == "reposearch":
        query = update.message.text.strip()
        sent = await update.message.reply_text("اختار مستودع للشات الجديد:\nبحث: " + query)
        await _show_repos(_MessageAdapter(sent), context, page=0, query=query)
    elif kind == "expired":
        await update.message.reply_text(
            "انتهت مهلة التوجيه (10 دقايق من آخر نشاط). افتح الشات تاني وابعت برومتك."
        )
    else:
        await update.message.reply_text("ابعت /start للقائمة، أو افتح شات عشان تبعتله برومت.")


async def cancel_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel: يلغي أي توجيه أو انتظار معلّق."""
    if not await _guard(update, context):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await update.message.reply_text("اتلغى التوجيه. ابعت /start للقائمة.")


async def cancel_route_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await _safe_edit(q, "اتلغى التوجيه ✅", reply_markup=kb.main_menu())


async def _send_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    conversation_id: str,
    text: str,
    title: str | None = None,
) -> None:
    """يسجّل البرومت في الصندوق (بثبات) قبل أي إرسال، ويرد 'وصل' فوراً."""
    if not text.strip():
        return
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    # نسجّل 'pending' قبل ما نبدأ أي إرسال، عشان البرومت مايضيعش لو العملية اتقطعت.
    # القرار 2: لو فيه برومت لنفس الوجهة اتسجّل خلال 1.5 ثانية، بيتجمّع معاه في سجل واحد.
    db.add_or_group_outbox(conversation_id, chat_id, text, outbox.now_iso())
    # تأكيد الحفظ بيذكر الشات المستهدف (القرار 1) عشان رسالة ماتروحش لشات غلط من غير ما تلاحظ.
    ack = "وصل ✅" if not title else f"وصل ✅ ← «{title[:40]}»"
    await update.message.reply_text(ack)
    worker = context.bot_data.get("outbox_worker")
    if worker is not None:
        # worker واحد مالك؛ بنوقّظه بدل ما نعمل task جديد لكل برومت.
        worker.wake()


async def _deliver_outbox(client, db, bot, outbox_id: int) -> None:
    await outbox.deliver_outbox(client, db, bot, outbox_id)


async def outbox_recover(app) -> None:
    await outbox.outbox_recover(app)


async def creation_recover(app) -> None:
    await outbox.creation_recover(app)


async def _conversation(client, conversation_id: str) -> dict:
    convs = await client.get_conversations([conversation_id])
    return convs[0] if convs else {}


async def start_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    await _show_repos(q, context, page=0, query="", user_id=update.effective_user.id)


_NAV_EXPIRED = "القايمة دي انتهت، افتح «شات جديد» من القائمة تاني."
_FILES_EXPIRED = "قايمة الملفات دي قديمة، افتح «الملفات» من الشات تاني."
_FILE_MISSING = "الملف مش موجود، افتح قايمة الملفات تاني."


def _repo_nav(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    return context.bot_data.setdefault("repo_nav", {}).get(user_id) or {}


async def repos_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    try:
        _, gen_raw, page_raw = q.data.split(":", 2)
        gen, page = int(gen_raw), int(page_raw)
    except ValueError:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu())
        return
    nav = _repo_nav(context, update.effective_user.id)
    if nav.get("gen") != gen:  # زر من قايمة أقدم
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu())
        return
    await _show_repos(q, context, page=page, query=nav.get("query", ""), user_id=update.effective_user.id)


async def repo_search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].set_awaiting(update.effective_user.id, "", "reposearch")
    await _safe_edit(q, "ابعت كلمة للبحث في المستودعات.")


async def _show_repos(
    q, context: ContextTypes.DEFAULT_TYPE, page: int, query: str, user_id: int | None = None
) -> None:
    client = context.bot_data["client"]
    if user_id is None:
        user_id = context.bot_data["config"].owner_id
    try:
        repos = await client.search_repositories(query=query)
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
        return
    start = page * REPOS_PAGE_SIZE
    chunk = repos[start : start + REPOS_PAGE_SIZE]
    if not chunk:
        await _safe_edit(q, "ما لقيتش مستودعات.", reply_markup=kb.main_menu())
        return
    # الأسماء الكاملة والبحث بيتخزّنوا هنا؛ الأزرار بتحمل رقم النسخة والفهرس بس (حد 64 بايت).
    gen = context.bot_data["repo_gen"] = context.bot_data.get("repo_gen", 0) + 1
    context.bot_data.setdefault("repo_nav", {})[user_id] = {
        "gen": gen,
        "query": query,
        "names": [r.get("full_name") or "" for r in repos],
    }
    has_more = len(repos) > start + REPOS_PAGE_SIZE
    title = "اختار مستودع للشات الجديد:" + (f"\nبحث: {query}" if query else "")
    await _safe_edit(
        q, title, reply_markup=kb.repositories_menu(chunk, page, has_more, gen, start=start)
    )


async def pick_repo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    try:
        _, gen_raw, idx_raw = q.data.split(":", 2)
        gen, idx = int(gen_raw), int(idx_raw)
    except ValueError:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu())
        return
    nav = _repo_nav(context, update.effective_user.id)
    names = nav.get("names") or []
    if nav.get("gen") != gen or not 0 <= idx < len(names) or not names[idx]:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu())
        return
    repo = names[idx]
    context.bot_data["db"].set_awaiting(update.effective_user.id, repo, "newchat")
    await _safe_edit(q, f"المستودع: {repo}\nابعت البرومت اللي عايز تبدأ بيه الشات (بعد 10 دقايق من غير رد هتتلغي).")


async def _start_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, repo: str | None, text: str) -> None:
    if not text.strip():
        return
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    # نسجّل طلب الشات الجديد (بثبات) قبل أي POST بدء، عشان مايضيعش لو العملية اتقطعت.
    db.add_creation_job(chat_id, repo, text, outbox.now_iso())
    await update.message.reply_text("وصل ✅ جاري بدء شات جديد.")
    worker = context.bot_data.get("creation_worker")
    if worker is not None:
        worker.wake()


async def _create_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, repo: str | None, text: str) -> None:
    """مسار متزامن مباشر (للاستخدام من الاختبارات): يسجّل job وينفّذه فوراً."""
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    bot = context.bot
    job_id = db.add_creation_job(chat_id, repo, text, outbox.now_iso())
    job = db.get_creation_job(job_id)
    await outbox._start_conversation(
        client, db, bot, job, context.bot_data["config"].openhands_base_url
    )


# ------------------------------------------------ manual outbox reconciliation
# أوامر المالك فقط لمراجعة/حل سجلات الصندوق الغامضة. كلها بتمر بـ _guard أولاً.
#
# مرجع السجل لازم يحدّد النوع صراحةً: "prompt:<id>" أو "creation:<id>". السبب إن
# جدولي outbox و creation_jobs معرّفاتهم الرقمية ممكن تتقاطع (1 في الاتنين)، فمرجع
# رقمي مجرّد كان يقدر يختار السجل الغلط. المرجع لازم يحل لجدول واحد وسجل واحد بس،
# وأي مرجع ناقص/غير صالح/غامض بيفشل مقفول (fail closed) من غير أي تغيير في الحالة.
_TERMINAL_OUTBOX = {"sent", "failed", "discarded"}
_TERMINAL_CREATION = {"done", "failed", "discarded"}

_REF_TYPES = {
    "prompt": ("outbox", "برومت"),
    "creation": ("creation", "طلب شات"),
}


def _safe_ts(value: str | None) -> str:
    """طابع زمني آمن للعرض (تاريخ + ساعة بدون كسور، وبدون أي بيانات حساسة)."""
    if not value:
        return "?"
    text = str(value).replace("T", " ")
    return text[:16]


def _parse_ref(token: str | None) -> tuple[str, int] | None:
    """يحلّل مرجع "<type>:<id>" لـ (نوع، معرّف). None لو ناقص/غير صالح/غامض.

    - النوع لازم يكون بالضبط "prompt" أو "creation" (بدون اختلاف حالة).
    - المعرّف لازم صحيح موجب.
    - أي مرجع رقمي مجرّد (بدون نوع) مرفوض عشان مايختارش جدول بالغلط.
    """
    if not token:
        return None
    raw = token.strip()
    if ":" not in raw:
        return None
    type_raw, _, id_raw = raw.partition(":")
    if type_raw not in _REF_TYPES:
        return None
    id_raw = id_raw.strip()
    if not id_raw.isdigit():
        return None
    value = int(id_raw)
    if value <= 0:
        return None
    return (type_raw, value)


def _get_record(db, ref: tuple[str, int]):
    """يرجّع السجل من الجدول اللي المرجع بيحدّده بالظبط (مش بحث في الاتنين)."""
    kind, rid = ref
    if kind == "prompt":
        return db.get_outbox(rid)
    return db.get_creation_job(rid)


def _outbox_usage(name: str) -> str:
    return f"استخدام: /{name} <prompt:id | creation:id> — مثال: /{name} prompt:3"


async def outbox_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox — عرض محدود للسجلات غير المنتهية (بدون نص البرومت أو أي أسرار)."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    items = db.list_open_outbox()
    jobs = db.list_open_creation_jobs()
    lines = ["📤 صندوق الصادر (غير المنتهي):"]
    if not items:
        lines.append("• مفيش برومتات معلّقة.")
    for item in items:
        lines.append(
            f"• prompt:{item.id} | الحالة: {item.status} | محاولات: {item.attempts} "
            f"| آخر تحديث: {_safe_ts(item.updated_at)}"
        )
    lines.append("🆕 طلبات شات جديد (غير المنتهية):")
    if not jobs:
        lines.append("• مفيش طلبات معلّقة.")
    for job in jobs:
        lines.append(
            f"• creation:{job.id} | الحالة: {job.status} | محاولات: {job.attempts} "
            f"| آخر تحديث: {_safe_ts(job.updated_at)}"
        )
    await update.message.reply_text("\n".join(lines))


async def outbox_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_status <prompt:id|creation:id> — تفاصيل سجل واحد بدون نص/أسرار."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_status"))
        return
    kind, rid = ref
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        return
    if kind == "prompt":
        await update.message.reply_text(
            f"برومت prompt:{record.id}\n"
            f"الحالة: {record.status}\n"
            f"المحادثة: {record.conversation_id}\n"
            f"محاولات: {record.attempts}\n"
            f"آخر خطأ: {record.error or '—'}\n"
            f"آخر تحديث: {_safe_ts(record.updated_at)}"
        )
        return
    await update.message.reply_text(
        f"طلب شات creation:{record.id}\n"
        f"الحالة: {record.status}\n"
        f"المستودع: {record.repo or '—'}\n"
        f"معرّف المهمة: {record.task_id or '—'}\n"
        f"المحادثة: {record.conversation_id or '—'}\n"
        f"محاولات: {record.attempts}\n"
        f"آخر خطأ: {record.error or '—'}\n"
        f"آخر تحديث: {_safe_ts(record.updated_at)}"
    )


async def outbox_discard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_discard <prompt:id|creation:id> confirm — يتخلّص من سجل (نهائي). idempotent."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_discard"))
        return
    kind, rid = ref
    label = _REF_TYPES[kind][1]
    if len(args) < 2 or args[1].strip().lower() != "confirm":
        await update.message.reply_text(
            f"تأكيد مطلوب: /outbox_discard {kind}:{rid} confirm\n"
            "ده هيعلّم السجل 'discarded' (نهائي) من غير أي إعادة إرسال."
        )
        return
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        return
    terminal = _TERMINAL_OUTBOX if kind == "prompt" else _TERMINAL_CREATION
    if record.status in terminal:
        await update.message.reply_text(
            f"{label} {kind}:{rid} خلاص في حالة نهائية ({record.status}) — مفيش تغيير."
        )
        return
    if kind == "prompt":
        db.set_outbox_status(rid, "discarded", outbox.now_iso(), "اتشال يدوياً")
    else:
        db.set_creation_status(rid, "discarded", outbox.now_iso(), "اتشال يدوياً")
    log.info("discard: ref=%s:%s status=discarded", kind, rid)
    await update.message.reply_text(f"تم تعليم {label} {kind}:{rid} كـ 'discarded'.")


async def outbox_mark_sent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_mark_sent <prompt:id|creation:id> confirm — تأكيد المالك إن العملية الغامضة نجحت."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_mark_sent"))
        return
    kind, rid = ref
    label = _REF_TYPES[kind][1]
    if len(args) < 2 or args[1].strip().lower() != "confirm":
        await update.message.reply_text(
            f"تأكيد مطلوب: /outbox_mark_sent {kind}:{rid} confirm\n"
            "ده تأكيد منك إن العملية نجحت فعلاً (مش إثبات من OpenHands). "
            "مش هيعيد أي إرسال، بس بيقفل السجل."
        )
        return
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        return
    if record.status == "unknown":
        # 'unknown' → حالة نهائية (sent/done): تفضل نهائية ومستحيل ترجع 'pending'،
        # فمفيش إعادة إرسال أو إنشاء تلقائي (at-most-once محفوظ).
        if kind == "prompt":
            db.set_outbox_status(rid, "sent", outbox.now_iso(), "أكّده المالك")
            final = "sent"
        else:
            db.set_creation_status(rid, "done", outbox.now_iso(), "أكّده المالك")
            final = "done"
        log.info("mark_sent: ref=%s:%s unknown->%s", kind, rid, final)
        await update.message.reply_text(
            f"تم تعليم {label} {kind}:{rid} كـ '{final}' (تأكيد منك — مش إثبات من OpenHands)."
        )
        return
    already = "sent" if kind == "prompt" else "done"
    if record.status == already:
        await update.message.reply_text(f"{label} {kind}:{rid} معَلّم '{already}' بالفعل — مفيش تغيير.")
        return
    await update.message.reply_text(
        f"{label} {kind}:{rid} حالته '{record.status}' — الأمر ده لـ 'unknown' بس."
    )
