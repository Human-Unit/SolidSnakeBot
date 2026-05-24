"""Handler for /search <query> command."""

import asyncio
import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.config import SYSTEM_PROMPT
from bot.llm import generate_reply
from bot.services.web_search import build_web_context
from bot.utils.text import split_message
from bot.utils.typing import keep_typing

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explicit web search: /search <query>"""
    from bot.handlers.message import histories, trim_history

    uid = update.effective_user.id
    query = " ".join(context.args).strip() if context.args else ""

    if not query:
        await update.message.reply_text(
            "...You didn't give me a target, Commander.\n"
            "Usage: /search <query>\n"
            "Example: /search Metal Gear REX schematics"
        )
        return

    if uid not in histories:
        histories[uid] = []

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        keep_typing(update.effective_chat.id, context.bot, stop_typing)
    )

    try:
        logger.info("[uid=%s] /search query: %r", uid, query)
        web_ctx = await build_web_context(query)

        if not web_ctx:
            await update.message.reply_text(
                "...Nothing came back on the wire, Commander.\n"
                "DuckDuckGo returned empty. The intel might be buried — or doesn't exist."
            )
            return

        full_user_message = (
            f"[Web recon — search results for: {query!r}]\n"
            f"{web_ctx}\n\n"
            f"[Commander's message]\n"
            f"Based on that web intel, answer my question: {query}"
        )

        llm_history = histories[uid] + [{"role": "user", "content": full_user_message}]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + llm_history

        reply = await generate_reply(messages)
        if not reply:
            reply = "...The codec is full of static. Repeat that, Commander."

        logger.info("[uid=%s] /search reply (%d chars): %r", uid, len(reply), reply[:150])

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error("[uid=%s] /search failed: %s", uid, e, exc_info=True)
        reply = (
            "...Interference on all channels.\n"
            "Either LM Studio went dark or DuckDuckGo is blocking the sweep.\n"
            "Check your six and try again."
        )
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    histories[uid].append({"role": "user", "content": f"[web search] {query}"})
    histories[uid].append({"role": "assistant", "content": reply})
    trim_history(uid)

    for chunk in split_message(reply):
        try:
            await update.message.reply_text(chunk)
        except BadRequest as e:
            logger.error("Telegram send error: %s", e)
            await update.message.reply_text(
                "...Transmission corrupted. Something went wrong on my end."
            )
            break
