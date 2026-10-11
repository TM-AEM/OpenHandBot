"""تجميع البوت: الربط، طابور الإرسال، والمراقب."""
from __future__ import annotations

import logging

from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import handlers
from .config import Config
from .db import Database
from .openhands_client import OpenHandsClient
from .watcher import Watcher

log = logging.getLogger(__name__)


def build_application(config: Config) -> Application:
    app = Application.builder().token(config.telegram_bot_token).build()
    client = OpenHandsClient(config.openhands_base_url, config.openhands_api_key)
    db = Database(config.db_path)

    app.bot_data["config"] = config
    app.bot_data["client"] = client
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CallbackQueryHandler(handlers.show_menu, pattern=r"^menu$"))
    app.add_handler(CallbackQueryHandler(handlers.list_conversations, pattern=r"^list:"))
    app.add_handler(CallbackQueryHandler(handlers.open_conversation, pattern=r"^open:"))
    app.add_handler(CallbackQueryHandler(handlers.show_status, pattern=r"^status:"))
    app.add_handler(CallbackQueryHandler(handlers.show_cost, pattern=r"^cost:"))
    app.add_handler(CallbackQueryHandler(handlers.export_conversation, pattern=r"^export:"))
    app.add_handler(CallbackQueryHandler(handlers.list_files, pattern=r"^files:"))
    app.add_handler(CallbackQueryHandler(handlers.show_file, pattern=r"^file:"))
    app.add_handler(CallbackQueryHandler(handlers.reply_prompt, pattern=r"^reply:"))
    app.add_handler(CallbackQueryHandler(handlers.start_new_chat, pattern=r"^newchat$"))
    app.add_handler(CallbackQueryHandler(handlers.repos_page, pattern=r"^repos:"))
    app.add_handler(CallbackQueryHandler(handlers.repo_search_prompt, pattern=r"^reposearch$"))
    app.add_handler(CallbackQueryHandler(handlers.pick_repo, pattern=r"^pickrepo:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))

    async def _post_init(application: Application) -> None:
        watcher = Watcher(
            client,
            db,
            application.bot,
            chat_id=config.owner_id,
            interval=config.watcher_interval,
        )
        application.bot_data["watcher"] = watcher
        watcher.start()

    async def _post_shutdown(application: Application) -> None:
        watcher: Watcher | None = application.bot_data.get("watcher")
        if watcher:
            await watcher.stop()
        await client.aclose()
        db.close()

    app.post_init = _post_init
    app.post_shutdown = _post_shutdown
    return app
