"""Application entrypoint for SolidSnakeBot."""

import asyncio
import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.config import TELEGRAM_BOT_TOKEN
from bot.handlers.commands import help_command, quote_command, reset, start, status_command
from bot.handlers.message import handle_message
from bot.handlers.search import search_command
from bot.llm import detect_model

logger = logging.getLogger(__name__)


def build_application():
    """Create the Telegram application and register public bot handlers."""
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def main() -> None:
    asyncio.run(detect_model())
    app = build_application()
    logger.info("Snake is on the codec. Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
