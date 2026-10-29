"""تجميع البوت: الربط، طابور الإرسال، والمراقب."""
from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import features, handlers
from .config import Config
from .db import Database
from .notifier import Notifier
from .openhands_client import OpenHandsClient
from .outbox import CreationWorker, OutboxWorker
from .watcher import Watcher

log = logging.getLogger(__name__)


def build_application(config: Config) -> Application:
    # U04: بدون concurrent_updates أي أمر بطيء (تصدير/قايمة ملفات) بيأخّر تأكيد
    # "وصل ✅" لأن التحديثات بتتعالج واحد ورا التاني. التزامن آمن هنا لأن حالة
    # التوجيه بتتستهلك ذرّياً (db.pop_awaiting) وكتابة الصندوق معاملة واحدة.
    app = Application.builder().token(config.telegram_bot_token).concurrent_updates(True).build()
    client = OpenHandsClient(config.openhands_base_url, config.openhands_api_key)
    db = Database(config.db_path)

    app.bot_data["config"] = config
    app.bot_data["client"] = client
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("cancel", handlers.cancel_route))
    app.add_handler(CommandHandler("notifications", handlers.notifications_command))
    app.add_handler(CommandHandler("outbox", handlers.outbox_list))
    app.add_handler(CommandHandler("outbox_status", handlers.outbox_status))
    app.add_handler(CommandHandler("outbox_discard", handlers.outbox_discard))
    app.add_handler(CommandHandler("outbox_mark_sent", handlers.outbox_mark_sent))
    app.add_handler(CallbackQueryHandler(handlers.show_menu, pattern=r"^menu$"))
    app.add_handler(CallbackQueryHandler(handlers.notifications_menu, pattern=r"^notif:menu$"))
    app.add_handler(CallbackQueryHandler(handlers.notifications_toggle, pattern=r"^notif:toggle$"))
    app.add_handler(CallbackQueryHandler(handlers.cancel_route_button, pattern=r"^cancelroute$"))
    app.add_handler(CallbackQueryHandler(handlers.list_conversations, pattern=r"^list:"))
    app.add_handler(CallbackQueryHandler(handlers.open_conversation, pattern=r"^open:"))
    app.add_handler(CallbackQueryHandler(handlers.copy_reply, pattern=r"^copy:"))
    app.add_handler(CallbackQueryHandler(handlers.full_reply, pattern=r"^full:"))
    app.add_handler(CallbackQueryHandler(handlers.show_status, pattern=r"^status:"))
    app.add_handler(CallbackQueryHandler(handlers.reply_prompt, pattern=r"^reply:"))
    app.add_handler(CallbackQueryHandler(handlers.start_new_chat, pattern=r"^newchat$"))
    app.add_handler(CallbackQueryHandler(handlers.repos_page, pattern=r"^repos:"))
    app.add_handler(CallbackQueryHandler(handlers.repo_search_prompt, pattern=r"^reposearch$"))
    app.add_handler(CallbackQueryHandler(handlers.pick_repo, pattern=r"^pickrepo:"))
    # القرار 4: الميزات المؤجّلة (الملفات/التصدير/التكلفة/إدارة المتابعات) مش بتتسجّل،
    # فحتى أي callback قديم مستني مش هيوصل لأي handler (نقاط الدخول مخفية). الكود والبيانات
    # لسه موجودين (مش بنحذف حاجة) — بس مش معروضين للمستخدم.
    if not features.is_hidden("followups"):
        app.add_handler(CallbackQueryHandler(handlers.list_watches, pattern=r"^watched:"))
        app.add_handler(CallbackQueryHandler(handlers.watch_conversation, pattern=r"^watch:"))
        app.add_handler(CallbackQueryHandler(handlers.unwatch_conversation, pattern=r"^unwatch:"))
    if not features.is_hidden("cost"):
        app.add_handler(CallbackQueryHandler(handlers.show_cost, pattern=r"^cost:"))
    if not features.is_hidden("export"):
        app.add_handler(CallbackQueryHandler(handlers.export_conversation, pattern=r"^export:"))
    if not features.is_hidden("files"):
        app.add_handler(CallbackQueryHandler(handlers.list_files, pattern=r"^files:"))
        app.add_handler(CallbackQueryHandler(handlers.show_file, pattern=r"^file:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    async def _post_init(application: Application) -> None:
        # 0) صيانة تشغيل آمنة: فحص سريع للتكامل + تحسين + checkpoint للـ WAL.
        #    لو القاعدة تالفة بنسجّل تحذير واضح بس البوت يفضل شغّال (ما بيرميش).
        db.run_startup_maintenance()
        # 1) تعافي الصندوق (يحوّل 'sending'/'starting' المتروك لـ 'unknown') قبل أي معالجة.
        await handlers.outbox_recover(application)
        await handlers.creation_recover(application)
        # 2) worker واحد مالك لكل جدول — يبدأوا بعد ما التعافي يخلص (عشان مايعالجوش
        #    سجل 'sending'/'starting' قبل ما يتحوّل 'unknown'). الحرس ده يمنع worker
        #    تاني لو اتنادت _post_init تاني (إعادة تهيئة مكرّرة).
        if application.bot_data.get("outbox_worker") is None:
            outbox_worker = OutboxWorker(client, db, application.bot)
            application.bot_data["outbox_worker"] = outbox_worker
            outbox_worker.start()
        if application.bot_data.get("creation_worker") is None:
            creation_worker = CreationWorker(
                client, db, application.bot, config.openhands_base_url
            )
            application.bot_data["creation_worker"] = creation_worker
            creation_worker.start()
        # حرس زي باقي الـ workers: إعادة تهيئة مكرّرة ما تعملش task مراقب تاني.
        if application.bot_data.get("watcher") is None:
            watcher = Watcher(
                client,
                db,
                application.bot,
                chat_id=config.owner_id,
                interval=config.watcher_interval,
                allowed_chats=config.allowed_telegram_ids,  # الشات الخاص id = id المستخدم
            )
            application.bot_data["watcher"] = watcher
            watcher.start()
        # المُبلّغ العام (NTF-03): إشعارات كل المحادثات. بيشارك نفس المراقب ملكية
        # الإشعارات المتابَعة (بيسجّل لقطتها بس بدون تسليم) عشان مفيش ازدواج.
        if application.bot_data.get("notifier") is None:
            notifier = Notifier(
                client,
                db,
                application.bot,
                chat_id=config.owner_id,
                interval=config.watcher_interval,
                base_url=config.openhands_base_url,
                allowed_chats=config.allowed_telegram_ids,
            )
            application.bot_data["notifier"] = notifier
            notifier.start()
        # نقطة التنسيق مع المُبلّغ: بعد ما تليجرام يأكّد إشعار مملوك للمراقب، بنسجّل الحالة
        # المعيارية عبر المُبلّغ **قبل** ما المتابعة تتشال (فما يعيدش نفس الإشعار). بنضبطها
        # هنا بعد إنشاء المُبلّغ (المراقب بيتعمل قبله). لو التسجيل فشل، المُبلّغ بيرميها
        # للمراقب اللي بيمنع الإزالة ويعيد المحاولة في دورة جاية.
        watcher = application.bot_data.get("watcher")
        notifier = application.bot_data.get("notifier")
        if watcher is not None and notifier is not None:
            watcher.set_owner_delivery(
                lambda conversation_id, status, now: notifier.record_notification_sent(
                    conversation_id, status, now
                )
            )

    async def _post_shutdown(application: Application) -> None:
        outbox_worker: OutboxWorker | None = application.bot_data.get("outbox_worker")
        if outbox_worker:
            await outbox_worker.stop()
        creation_worker: CreationWorker | None = application.bot_data.get("creation_worker")
        if creation_worker:
            await creation_worker.stop()
        watcher: Watcher | None = application.bot_data.get("watcher")
        if watcher:
            await watcher.stop()
        notifier: Notifier | None = application.bot_data.get("notifier")
        if notifier:
            await notifier.stop()
        await client.aclose()
        # إغلاق نظيف: نرجّع بيانات WAL للقاعدة الرئيسية ونقصّر الـ WAL.
        try:
            db.checkpoint()
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("checkpoint عند الإغلاق اتخطّى (%s)", type(exc).__name__)
        db.close()

    app.post_init = _post_init
    app.post_shutdown = _post_shutdown
    return app
