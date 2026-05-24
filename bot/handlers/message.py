"""Main text message handler."""

import asyncio
import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.config import SYSTEM_PROMPT, MAX_HISTORY
from bot.llm import generate_reply
from bot.rag import retrieve_context
from bot.services.currency import get_cbr_currency_rates, is_currency_question
from bot.services.web_search import build_web_context, should_use_web, is_schedule_question
from bot.utils.text import split_message
from bot.utils.typing import keep_typing

logger = logging.getLogger(__name__)

# ─── Conversation memory ─────────────────────────────────────────
histories: dict[int, list[dict]] = {}


def trim_history(uid: int) -> None:
    h = histories[uid]
    limit = MAX_HISTORY * 2
    if len(h) > limit:
        h = h[-limit:]
        if h and h[0]["role"] == "assistant":
            h.pop(0)
        histories[uid] = h


# ─── Handler ─────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    if uid not in histories:
        histories[uid] = []

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        keep_typing(update.effective_chat.id, context.bot, stop_typing)
    )

    try:
        context_parts: list[str] = []

        # RAG retrieval
        intel = retrieve_context(user_text)
        if intel:
            context_parts.append(f"[Knowledge base]\n{intel}")

        # Currency — direct API, no web search needed
        if is_currency_question(user_text):
            rates = await get_cbr_currency_rates()
            if rates:
                context_parts.append(f"[Currency rates]\n{rates}")

        # Web search — for explicit triggers or schedule questions
        elif should_use_web(user_text) or is_schedule_question(user_text):
            web_ctx = await build_web_context(user_text)
            if web_ctx:
                context_parts.append(f"[Web recon]\n{web_ctx}")

        if context_parts:
            full_user_message = (
                "[Mission intel — classified background context]\n"
                + "\n\n".join(context_parts)
                + f"\n\n[Commander's message]\n{user_text}"
            )
        else:
            full_user_message = user_text

        llm_history = histories[uid] + [{"role": "user", "content": full_user_message}]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + llm_history

        reply = await generate_reply(messages)
        if not reply:
            reply = "...The codec is full of static. Repeat that, Commander."

        logger.info("[uid=%s] reply (%d chars): %r", uid, len(reply), reply[:150])

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error("[uid=%s] LLM call failed: %s", uid, e, exc_info=True)
        reply = (
            "...Snake here. I'm reading nothing but interference on this channel.\n"
            "LM Studio may be offline — or something worse.\n"
            "Check the link and try again, Commander."
        )
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    histories[uid].append({"role": "user", "content": user_text})
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
