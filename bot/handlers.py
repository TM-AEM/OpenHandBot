"""أوامر تيليجرام وأزرارها. كل الرسايل عربي، والمستخدم المالك بس يترد عليه."""
from __future__ import annotations

import io
import logging
import sqlite3
import time

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from . import keyboards as kb
from . import outbox
from . import deletion
from .errors import ApiError, ResponseTooLargeError, error_text
from .file_cache import FileCache
from .openhands_client import collect_conversations
from .files import (
    CONVERSATION_ERRORS,
    FileService,
    FileStatus,
    authorize_conversation_detailed,
    file_status_message,
)
from .messages import escape_html, format_conversation_view, format_cost, pr_url, state_label
from .sender import send_copyable, send_long

log = logging.getLogger(__name__)

PAGE_SIZE = 10
REPOS_PAGE_SIZE = 8
FILES_PAGE_SIZE = 10
# TASK 55 (المرحلة B/C): كاش قصير للتبادل الأخير (copy/full) وكاش قايمة الشاتات.
# الرام محدود (308MB على Katabump) فبنحدّ عدد المداخل.
EXCHANGE_TTL = 45.0
EXCHANGE_CACHE_MAX = 20
LIST_TTL = 45.0


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


async def _edit_or_send(query, text: str, chat_id: int, bot, **kwargs) -> bool:
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


def _identity_cache(context: ContextTypes.DEFAULT_TYPE):
    """كاش هوية المالك المشترك على مستوى البوت (OHB2-09-A2-04).

    مربوط بالعميل المشترك الواحد (`bot_data["client"]`) عشان `/users/me` يتنادى مرة
    واحدة عبر كل مسارات الشات في البوت. الكاش مقيّد بالعميل: لو العميل اتغيّر (بناء
    جديد) بنعمل كاش جديد، فما يتسرّبش بين اعتمادين/جلسات.
    """
    from .files import IdentityCache

    client = context.bot_data["client"]
    entry = context.bot_data.get("identity_cache")
    if entry is not None and entry[0] is client:
        return entry[1]
    cache = IdentityCache(client)
    context.bot_data["identity_cache"] = (client, cache)
    return cache


def _files_service(context: ContextTypes.DEFAULT_TYPE) -> FileService:
    """`FileService` فوق نفس العميل المشترك وكاش الهوية المشترك (مفيش عميل تاني)."""
    return FileService(context.bot_data["client"], identity=_identity_cache(context))


async def _authorized_conversation(client, context: ContextTypes.DEFAULT_TYPE, conversation_id: str):
    """يفوّض شات عبر **نفس** تنفيذ `FileService` (ملكية/معرّف/فشل مغلق).

    يرجّع `(conv | None, message)`؛ لو `conv` فاضي فـ `message` رسالة عربي آمنة. عند
    فشل upstream (429/503/مهلة/انقطاع) بنعرض رسالة الخطأ المتنقّحة (زي مسار البوت
    القديم)، ولسه **مفيش أي جلب بيانات محمية** غير الميتاداتا المتفوَّض عليها.
    """
    conv, status, error = await authorize_conversation_detailed(
        client, _identity_cache(context), conversation_id
    )
    if conv is not None:
        return conv, None
    if status is FileStatus.UPSTREAM_ERROR and error:
        return None, error  # رسالة ApiError متنقّحة (نفس سلوك مسار open القديم)
    _code, _http, message = CONVERSATION_ERRORS.get(
        status, ("upstream_error", 502, "تعذّر الوصول للشات دلوقتي، جرّب تاني.")
    )
    return None, message


def _store_exchange(context, conversation_id, user_text, reply):
    """يخزّن آخر تبادل (برومت مستخدم + رد agent) لكاش قصير، ويحافظ على الحد الأقصى."""
    cache = context.bot_data.setdefault("exchange_cache", {})
    cache[conversation_id] = (time.monotonic(), user_text, reply)
    while len(cache) > EXCHANGE_CACHE_MAX:
        cache.pop(next(iter(cache)))  # الأقدم أولاً (ترتيب الإدخال)


async def _get_exchange(context, conversation_id):
    """آخر تبادل من الكاش لو لسه طازة، وإلا من الـ API (وبيخزّنه).

    الكاش بيخدم أزرار copy/full بس — فتح الشات (open) بيقرا طازة دايماً.
    """
    cache = context.bot_data.setdefault("exchange_cache", {})
    hit = cache.get(conversation_id)
    if hit and time.monotonic() - hit[0] < EXCHANGE_TTL:
        return hit[1], hit[2]
    user_text, reply = await context.bot_data["client"].get_last_exchange(conversation_id)
    _store_exchange(context, conversation_id, user_text, reply)
    return user_text, reply


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


def _mini_app_url(context: ContextTypes.DEFAULT_TYPE) -> str:
    """رابط الـ Mini App لو الميزة **مفعّلة** ومهيّأة، وإلا فاضي.

    لازم الاتنين: `MINI_APP_ENABLED=1` **و** رابط `MINI_APP_URL` صالح. كده ما بنعرضش
    زر web_app لرابط ميت (الميزة مفعّلة بلا سيرفر شغّال، أو رابط بدون تفعيل).
    """
    cfg = context.bot_data.get("config")
    if cfg is None or not getattr(cfg, "mini_app_enabled", False):
        return ""
    return getattr(cfg, "mini_app_url", "") or ""


def _mini_app_diagnostic(context: ContextTypes.DEFAULT_TYPE) -> str:
    """سبب عدم إتاحة الـ Mini App — **بدون أي أسرار** (أسماء إعدادات بس)."""
    cfg = context.bot_data.get("config")
    if cfg is None:
        return "الإعداد غير متاح."
    if not getattr(cfg, "mini_app_enabled", False):
        return "الميزة مقفولة (MINI_APP_ENABLED=0)."
    if not (getattr(cfg, "mini_app_url", "") or ""):
        return "الرابط العام (MINI_APP_URL) غير مهيّأ."
    return "الإعداد غير مكتمل."


MINI_APP_UNAVAILABLE = (
    "التطبيق المصغّر مش متاح دلوقتي. الأوامر والأزرار العادية شغالة زي ما هي."
)


HELP_TEXT = (
    "أنا بوت تحكمك في OpenHands Cloud. الأوامر المتاحة:\n"
    "/start — القائمة الرئيسية\n"
    "/app — فتح التطبيق المصغّر (Mini App)\n"
    "/help — هذه المساعدة\n"
    "/notifications — ضبط الإشعارات الاستباقية\n"
    "/cancel — إلغاء التوجيه الحالي\n"
    "\n"
    "صيانة الصندوق (للمالك):\n"
    "/outbox — السجلات المعلّقة\n"
    "/outbox_status — تفاصيل سجل واحد\n"
    "/outbox_discard — شطب سجل (يتطلب confirm)\n"
    "/outbox_mark_sent — تأكيد إرسال سجل (يتطلب confirm)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await update.message.reply_text(
        "أهلاً 👋\nأنا بوت تحكمك في OpenHands Cloud.\n"
        "اختار من الأزرار تحت، أو افتح شات وابعتله برومت.",
        reply_markup=kb.main_menu(_mini_app_url(context)),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    await update.message.reply_text(HELP_TEXT)


async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    url = _mini_app_url(context)
    if not url:
        await update.message.reply_text(
            f"{MINI_APP_UNAVAILABLE}\nالسبب: {_mini_app_diagnostic(context)}"
        )
        return
    await update.message.reply_text("افتح التطبيق من الزر:", reply_markup=kb.mini_app_launch(url))


async def app_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    url = _mini_app_url(context)
    if not url:
        await q.edit_message_text(
            f"{MINI_APP_UNAVAILABLE}\nالسبب: {_mini_app_diagnostic(context)}",
            reply_markup=kb.main_menu(_mini_app_url(context)),
        )
        return
    await q.edit_message_text("افتح التطبيق من الزر:", reply_markup=kb.mini_app_launch(url))


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    await q.edit_message_text(
        "أهلاً 👋 اختار من الأزرار:", reply_markup=kb.main_menu(_mini_app_url(context))
    )


def _notifications_text(enabled: bool) -> str:
    state = "مفعّلة ✅" if enabled else "متوقفة ⛔"
    return (
        f"إشعارات OpenHands الاستباقية: {state}\n\n"
        "لما تكون مفعّلة، هبلّغك لما أي محادثة توصل لحالة نهائية "
        "(انتهت/خطأ/متعلّقة/مستنية تأكيد/خطأ بيئة).\n"
        "الإيقاف بيوقف الإشعارات الاستباقية بس — باقي أوامر البوت وأزراره زي ما هي."
    )


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    await update.message.reply_text(
        _notifications_text(db.get_notifications_enabled()),
        reply_markup=kb.notifications_menu(db.get_notifications_enabled()),
    )


async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    db = context.bot_data["db"]
    enabled = db.get_notifications_enabled()
    await q.edit_message_text(_notifications_text(enabled), reply_markup=kb.notifications_menu(enabled))


async def notifications_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not _allowed(update, context.bot_data["config"]):
        await q.answer()
        return
    db = context.bot_data["db"]
    new_state = not db.get_notifications_enabled()
    db.set_notifications_enabled(new_state)
    await q.answer("تم التحديث ✅")
    await q.edit_message_text(
        _notifications_text(new_state), reply_markup=kb.notifications_menu(new_state)
    )


def _without_deleted(db, items: list[dict]) -> list[dict]:
    """يشيل الشاتات المحذوفة محليًا (tombstone) من قايمة شاتات البوت (OHB2-F1).

    القايمة بتيجي من بحث بعيد مش عارف بالحذف المحلي، فبندمجها مع شاهد الحذف قبل الترقيم
    عشان الشات المحذوف ما يظهرش لا من كاش قديم ولا من بحث جديد.

    OHB2-AUDIT-FIX-04 (فشل مغلق): لو تعذّر قراءة شواهد الحذف (قاعدة غير متاحة)، بنرجّع
    قايمة **فاضية** بدل القايمة غير المفلترة. الادّعاء إن شات «مش محذوف» لما إحنا مش قادرين
    نتأكّد أسوأ من إظهار «مفيش شاتات» مؤقتًا — الإظهار بالغلط أثر أمني/خصوصية (شات اتحذف
    بيبان تاني)، بينما الإخفاء بالغلط transient وبيتحلّ بمجرد رجوع القاعدة.
    """
    if not items:
        return items
    try:
        return [c for c in items if not db.is_deleted(c.get("id") or "")]
    except Exception:  # noqa: BLE001 — قاعدة غير متاحة ⇒ نفشل مقفولين (مفيش إظهار بالغلط)
        log.warning("تعذّر قراءة شواهد الحذف؛ بنخفي القايمة مؤقتًا (فشل مغلق).")
        return []


async def list_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    page = int(q.data.split(":", 1)[1])
    client = context.bot_data["client"]
    # نجيب كل صفحات البحث (نتبع next_page_id بحد أقصى). `collect_conversations` بيرجّع
    # القايمة مرتّبة بـ `updated_at` تنازليًا وبدون تكرارات (عقد ترتيب صريح، مش معتمد على
    # ترتيب الـ API الخام) — فالترقيم ثابت عبر الصفحات.
    # TASK 55 (G4): كاش قصير للقايمة عشان الضغط على «المزيد» ما يعملش طلب API كل مرة.
    cache = context.bot_data.get("list_cache")
    if cache and time.monotonic() - cache[0] < LIST_TTL:
        items = cache[1]
        truncated = cache[2] if len(cache) > 2 else False
    else:
        try:
            collected = await collect_conversations(client)
        except ApiError as exc:
            await _safe_edit(q, error_text(exc))
            return
        items = collected["items"]
        truncated = collected["truncated"]
        if items:
            context.bot_data["list_cache"] = (time.monotonic(), items, truncated)
    # OHB2-F1: الشاتات المحذوفة محليًا لازم تختفي من القايمة قبل الترقيم — سواء جاية من
    # كاش قديم أو من بحث بعيد جديد (البحث مش عارف بالحذف المحلي).
    items = _without_deleted(context.bot_data["db"], items)
    if not items:
        await _safe_edit(q, "ما فيهاش شاتات.", reply_markup=kb.main_menu(_mini_app_url(context)))
        return
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        page, start = 0, 0
        chunk = items[:PAGE_SIZE]
    has_more = len(items) > start + PAGE_SIZE
    header = f"آخر الشاتات (صفحة {page + 1}):"
    if truncated:
        # OHB2-AUDIT-FIX-05: القايمة أطول من الحد المسموح ⇒ نعلن ده بدل إخفاء صامت.
        header += f"\n(القايمة طويلة — بنعرض أحدث {len(items)} شات.)"
    await _safe_edit(
        q,
        header,
        reply_markup=kb.conversations_menu(chunk, page, has_more),
    )


async def open_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    # OHB2-09-06: تفويض ملكية الشات أولًا (نفس عقد FileService)، بعدين نجيب آخر تبادل طازة.
    # (فتح الشات بيقرا طازة دايماً — مش من كاش copy/full.)
    conv, message = await _authorized_conversation(client, context, conversation_id)
    if conv is None:
        await _edit_or_send(q, message, q.message.chat_id, context.bot)
        return
    try:
        user_text, reply = await client.get_last_exchange(conversation_id)
    except ApiError as exc:
        # نفس المسار المتسامح لرسالة الخطأ: مفيش توجيه جديد ولا انهيار في الـ callback.
        await _edit_or_send(q, error_text(exc), q.message.chat_id, context.bot)
        return
    _store_exchange(context, conversation_id, user_text, reply)
    db = context.bot_data["db"]
    watched = db.is_watched(conversation_id)
    text, reply_cut = format_conversation_view(conv, user_text, reply)
    text += "\n\n✉️ رسايلك الجاية هتتبعت للشات ده (10 دقايق من آخر نشاط). للإلغاء: زر إلغاء التوجيه أو /cancel."
    markup = kb.conversation_actions(
        conversation_id, watched, has_reply=reply is not None, reply_cut=reply_cut
    )
    # القرار 1: بعد فتح الشات، رسايلك الجاية بتتوجّه له 10 دقايق من آخر نشاط (مع زر إلغاء).
    # بنفعّل التوجيه بس بعد ما العرض يظهر فعلاً، عشان فشل العرض ما يسبش توجيه مفعّل من غير
    # ما تشوف الشات (وما نلمسش أي توجيه قائم لو الفتح فشل).
    if await _edit_or_send(q, text, q.message.chat_id, context.bot, reply_markup=markup):
        db.set_awaiting(update.effective_user.id, conversation_id, "route", title=conv.get("title") or "")


async def copy_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TASK 55 (المرحلة B): يبعت رد الـ agent جوه code block قابل للنسخ بضغطة."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id
    # OHB2-09-06: تفويض ملكية الشات قبل قراءة آخر تبادل (نفس عقد FileService).
    _conv, message = await _authorized_conversation(context.bot_data["client"], context, conversation_id)
    if _conv is None:
        await context.bot.send_message(chat_id, escape_html(message), parse_mode=ParseMode.HTML)
        return
    try:
        _, reply = await _get_exchange(context, conversation_id)
    except ApiError as exc:
        await context.bot.send_message(chat_id, escape_html(error_text(exc)), parse_mode=ParseMode.HTML)
        return
    if not reply:
        await context.bot.send_message(chat_id, "لسه مفيش رد للشات ده.")
        return
    await send_copyable(chat_id, reply, context.bot)


async def full_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TASK 55 (المرحلة B): يبعت الرد الكامل (نفس منطق send_long)."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id
    # OHB2-09-06: تفويض ملكية الشات قبل قراءة آخر تبادل (نفس عقد FileService).
    _conv, message = await _authorized_conversation(context.bot_data["client"], context, conversation_id)
    if _conv is None:
        await context.bot.send_message(chat_id, escape_html(message), parse_mode=ParseMode.HTML)
        return
    try:
        _, reply = await _get_exchange(context, conversation_id)
    except ApiError as exc:
        await context.bot.send_message(chat_id, escape_html(error_text(exc)), parse_mode=ParseMode.HTML)
        return
    if not reply:
        await context.bot.send_message(chat_id, "لسه مفيش رد للشات ده.")
        return
    await send_long(chat_id, reply, context.bot)


async def list_watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    page = int(q.data.split(":", 1)[1])
    items = context.bot_data["db"].list_watched()
    if not items:
        await _safe_edit(q, "مفيش شاتات متابَعة.", reply_markup=kb.main_menu(_mini_app_url(context)))
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
    # OHB2-09-06/A2-02: نفس عقد ملكية الشات قبل الإضافة (مفيش شات غير مملوك للمتابعة).
    conv, message = await _authorized_conversation(client, context, conversation_id)
    if conv is None:
        await _safe_edit(q, message)
        return
    # NTF-19: لو الشات متابَع بالفعل، الضغطة دي إعادة نداء مكرّرة (double-tap) ⇒ نحافظ على
    # المعرّف والعلامة المعلّقة (new_lifecycle=False). لو مش متابَع، الصف مش موجود فالـ INSERT
    # بيعمل دورة جديدة بمعرّف جديد تلقائيًا.
    db.add_watched(
        conversation_id, conv.get("title", ""), q.message.chat_id,
        new_lifecycle=False, reengage=True,
    )
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
    # NTF-17: نمرّ عبر المراقب (لو موجود) عشان أي تسليم معلّق في الذاكرة يتكمّل ذرّيًا،
    # ومايحصلش إرسال مكرّر بعد إزالة المتابعة.
    watcher = context.bot_data.get("watcher")
    remover = watcher.unwatch if watcher is not None else context.bot_data["db"].remove_watched
    try:
        remover(conversation_id)
    except sqlite3.Error:
        log.exception("تعذّر إزالة متابعة الشات %s", conversation_id)
        # نبني نفس قائمة المتابعات تاني عشان زر المحاولة يفضل متاح (الشات لسه متابَع).
        try:
            items = context.bot_data["db"].list_watched()
            markup = kb.watches_menu(items[:PAGE_SIZE], 0, len(items) > PAGE_SIZE)
        except sqlite3.Error:
            markup = None
        await _safe_edit(
            q,
            "تعذّر إلغاء المتابعة دلوقتي (خطأ مؤقت في قاعدة البيانات). جرّب تاني.",
            reply_markup=markup,
        )
        return
    await _safe_edit(q, "تمام، اتشال من المتابعة.")


async def delete_conversation_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-MINIAPP: يعرض تأكيد حذف الشات **من OpenHands**. تفويض الملكية قبل أي حذف."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
        return
    title = conv.get("title") or "بدون عنوان"
    await _safe_edit(
        q,
        f"متأكد إنك عايز تحذف الشات «{title}»؟\n"
        "ده هيحذفه نهائيًا من OpenHands نفسه (مش إخفاء محلي) — العملية مش قابلة للرجوع.",
        reply_markup=kb.delete_confirm_menu(conversation_id),
    )


async def delete_conversation_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-MINIAPP: تأكيد حذف الشات **من OpenHands** ثم محليًا. تفويض الملكية إلزامي."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    # تفويض الملكية **قبل** أي حذف — العميل بيبعت المعرّف بس، والملكية بتتأكد server-side.
    conv, message = await _authorized_conversation(client, context, conversation_id)
    if conv is None:
        await _safe_edit(q, message)
        return
    try:
        result = await deletion.delete_conversation_remote(client, db, conversation_id)
    except sqlite3.Error:
        log.exception("تعذّر حذف الشات %s", conversation_id)
        await _safe_edit(q, "تعذّر الحذف دلوقتي (خطأ مؤقت في قاعدة البيانات). جرّب تاني.")
        return
    # نجاح الحذف (المؤكّد) ⇒ ترتيب/محتوى القايمة اتغيّر ⇒ نبطّل كاش القايمة (زي البرومت/
    # بدء الشات). مابنبطّلوش في حالات الفشل/النتيجة المجهولة (الشات ممكن لسه بعيدًا).
    if result.status == deletion.STATUS_DELETED:
        context.bot_data.pop("list_cache", None)
    await _safe_edit(
        q,
        result.message,
        reply_markup=kb.main_menu(_mini_app_url(context)),
    )


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    conversation_id = q.data.split(":", 1)[1]
    # OHB2-09-06: تفويض الشات عبر نفس عقد FileService (ملكية + فشل مغلق) قبل أي عرض.
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
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
    # OHB2-09-A2-02: نفس عقد ملكية الشات قبل قراءة المقاييس (بدل get_conversations الخام).
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
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
    # OHB2-09-A2-01: تفويض على مستوى الشات **قبل أي تنزيل** — نفس عقد FileService
    # (المعرّف + هوية المالك من /users/me + `created_by_user_id`، وفشل مغلق). بنستخدم
    # نفس خدمة الملفات المشتركة عشان مايبقاش فيه نسخة تانية من منطق التفويض.
    conv, message = await _authorized_conversation(client, context, conversation_id)
    if conv is None:
        log.info("export: رفض تفويض الشات (ref=%s)", conversation_id)
        await _safe_edit(q, message)
        return
    try:
        data = await client.export_conversation(conversation_id)
    except ResponseTooLargeError:
        # OHB2-09-06: التصدير محدود؛ عدّى الحد ⇒ رسالة صريحة (مش خطأ عام)، مفيش مستند.
        await _safe_edit(q, "التصدير كبير أوي للتنزيل الآمن. جرّب شات أصغر.")
        return
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
    # OHB2-09-06: عبر FileService المشترك (تفويض الملكية + allowlist للمسارات الآمنة).
    listing = await _files_service(context).list_files(conversation_id)
    if listing.status is not FileStatus.OK:
        await _safe_edit(q, file_status_message(listing.status, listing.error))
        return
    files = list(listing.files)
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
    # OHB2-09-06: قراءة **محدودة** عبر FileService (allowlist + حد صلب + تصنيف نص)،
    # مش `client.read_file` غير المحدود. يمنع تحميل ملف ضخم في الذاكرة.
    content = await _files_service(context).read_preview(conversation_id, path)
    if content.status is not FileStatus.OK:
        # ثنائي/ترميز غير مدعوم/كبير/مش موجود/غير مصرّح ⇒ رسالة واضحة بدل محتوى مشوّه.
        await _safe_edit(q, file_status_message(content.status, content.error))
        return
    body = content.text or ""
    name = path.rsplit("/", 1)[-1] or "file.txt"
    if content.truncated:
        body += "\n\n… (المعاينة مقصوصة — الملف أكبر من حد العرض الآمن.)"
    buffer = io.BytesIO(body.encode("utf-8"))
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
    # OHB2-09-A2-02/B2-06-04: تفويض ملكية الشات **قبل** أي توجيه لبرومت — نفس عقد
    # باقي مسارات الشات (ملفات/حالة/تفاصيل/تصدير). كده مايتفتحش توجيه برومت لشات
    # مش مملوك (فشل مغلق عند غياب/عدم تطابق المالك).
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
        return
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
    await _safe_edit(q, "اتلغى التوجيه ✅", reply_markup=kb.main_menu(_mini_app_url(context)))


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
    db.add_or_group_outbox(conversation_id, chat_id, text, outbox.now_iso(), reengage=True)
    # TASK 55 (C): ترتيب القايمة بيتغيّر بعد البرومت ⇒ نبطّل كاش القايمة.
    context.bot_data.pop("list_cache", None)
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
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        return
    nav = _repo_nav(context, update.effective_user.id)
    if nav.get("gen") != gen:  # زر من قايمة أقدم
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
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
        await _safe_edit(
            q,
            "ما لقيتش مستودعات. تقدر تبدأ شات بدون مستودع.",
            reply_markup=kb.repos_empty_menu(),
        )
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
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        return
    nav = _repo_nav(context, update.effective_user.id)
    names = nav.get("names") or []
    if nav.get("gen") != gen or not 0 <= idx < len(names) or not names[idx]:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        return
    repo = names[idx]
    context.bot_data["db"].set_awaiting(update.effective_user.id, repo, "newchat")
    await _safe_edit(q, f"المستودع: {repo}\nابعت البرومت اللي عايز تبدأ بيه الشات (بعد 10 دقايق من غير رد هتتلغي).")


async def new_chat_no_repo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شات جديد من غير مستودع (المهمة OHB2: إنشاء شات بمستودع أو بدونه)."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        return
    context.bot_data["db"].set_awaiting(update.effective_user.id, None, "newchat")
    await _safe_edit(
        q,
        "شات من غير مستودع.\nابعت البرومت اللي عايز تبدأ بيه الشات (بعد 10 دقايق من غير رد هتتلغي).",
    )


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
    """مسار متزامن مباشر (للاستخدام من الاختبارات): يسجّل job وينفّذه فوراً.

    (الحماية الذرّية لحدّ الإلغاء بتحصل جوه `_start_conversation`: CAS 'pending'/'claimed'
    ⇒ 'starting' قبل الـ POST، فأي شطب متزامن يوقف الإرسال الفعلي.)
    """
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    bot = context.bot
    job_id = db.add_creation_job(chat_id, repo, text, outbox.now_iso())
    job = db.get_creation_job(job_id)
    await outbox._start_conversation(
        client, db, bot, job, context.bot_data["config"].openhands_base_url
    )
    # TASK 55 (C): بعد نجاح بدء الشات، ترتيب القايمة اتغيّر ⇒ نبطّل كاش القايمة.
    context.bot_data.pop("list_cache", None)


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
    # OHB2-N10-28C: شطب **ذرّي** مع حدّ إلغاء واضح. الشطب بيتنفّذ بس لو لسه مؤهّل قبل
    # الإرسال (pending/claimed). لو الـ POST ممكن يكون بدأ (sending/unknown) ما بنشطبش
    # وما بندّعيش إلغاء — بنبلّغ إن الإلغاء غير مؤكد ونسيب السجل للاستعلام/التسوية.
    if kind == "prompt":
        outcome = db.discard_outbox(rid, outbox.now_iso(), "اتشال يدوياً")
    else:
        outcome = db.discard_creation_job(rid, outbox.now_iso(), "اتشال يدوياً")
    if outcome == "discarded":
        log.info("discard: ref=%s:%s status=discarded", kind, rid)
        await update.message.reply_text(f"تم تعليم {label} {kind}:{rid} كـ 'discarded'.")
        return
    if outcome == "not_confirmed":
        # الشطب بعد ما الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء (C2 Case 3).
        await update.message.reply_text(
            f"{label} {kind}:{rid} ممكن يكون بدأ الإرسال بالفعل — الإلغاء غير مؤكد.\n"
            "استعلم عن الحالة من الموقع، ولو مش متأكد استخدم /outbox_status أو /outbox_mark_sent."
        )
        return
    # بين القراءة والشطب حد تاني حسم السجل (نهائي) ⇒ مفيش تغيير.
    current = _get_record(db, ref)
    status_now = current.status if current is not None else "؟"
    await update.message.reply_text(
        f"{label} {kind}:{rid} خلاص في حالة نهائية ({status_now}) — مفيش تغيير."
    )


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
        # فمفيش إعادة إرسال أو إنشاء تلقائي (at-most-once محفوظ). OHB2-N10-28C: CAS ذرّي
        # من 'unknown' بس، عشان ما نقلبش حالة أحدث حسمها حد تاني (مفيش read-then-write).
        if kind == "prompt":
            changed = db.set_outbox_status_if_in(
                rid, "sent", outbox.now_iso(), {"unknown"}, "أكّده المالك"
            )
            final = "sent"
        else:
            changed = db.set_creation_status_if_in(
                rid, "done", outbox.now_iso(), {"unknown"}, "أكّده المالك"
            )
            final = "done"
        if not changed:
            # سبقنا كاتب تاني وحسم السجل بين القراءة والكتابة ⇒ ما نغيّرش حاجة.
            current = _get_record(db, ref)
            status_now = current.status if current is not None else "؟"
            if status_now == final:
                await update.message.reply_text(
                    f"{label} {kind}:{rid} معَلّم '{final}' بالفعل — مفيش تغيير."
                )
            else:
                await update.message.reply_text(
                    f"{label} {kind}:{rid} حالته '{status_now}' — الأمر ده لـ 'unknown' بس."
                )
            return
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
