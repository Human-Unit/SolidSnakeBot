"""Bot command handlers: /start, /reset, /help, /quote, /status."""

import logging
import random

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import LM_STUDIO_BASE_URL
from bot.rag import documents

logger = logging.getLogger(__name__)

ICONIC_QUOTES = [
    "Life isn't just about passing on your genes. We can leave behind much more than that.",
    "I'm no hero. Never was, never will be.",
    "War has changed. It's no longer about nations, ideologies, or ethnicity. It's an endless series of proxy battles fought by mercenaries and machines.",
    "The only thing we can do is to pass things on to the next generation.",
    "A strong man doesn't need to read the future. He makes his own.",
    "I live in a world of death... and those who deal in it.",
    "Kept you waiting, huh?",
    "Nothing personal... this is the mission.",
    "There's no point in living if you can't fight for something worth dying for.",
    "Outer Heaven is built on military force alone — power without spirit.",
    "There are no heroes in war. The only heroes I know are either dead or in prison.",
    "Otacon... this isn't over yet. Not by a long shot.",
    "We're not tools of the government, or anyone else. Fighting was the only thing... the only thing I was good at.",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers.message import histories
    uid = update.effective_user.id
    histories[uid] = []
    await update.message.reply_text(
        "...Snake here.\n\n"
        "Codec is open, Commander. "
        "I don't know how you found this frequency, but you did — so you must need something.\n\n"
        "Give me your objective. Whether it's a debrief, technical intel, or something you can't explain to anyone else — I'm listening.\n\n"
        "Commands:\n"
        "/help          — operational overview\n"
        "/search <query> — sweep the web for intel\n"
        "/quote         — a transmission from the field\n"
        "/reset         — wipe the codec history\n"
        "/status        — check LM Studio link"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.handlers.message import histories
    uid = update.effective_user.id
    histories[uid] = []
    await update.message.reply_text(
        "...Memory wiped.\n"
        "Whatever we discussed — it's gone. Like it never happened.\n\n"
        "Codec channel open. New objective, Commander?"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "...You need a briefing. Fine.\n\n"
        "I'm Snake. You're the Commander. This is a codec channel.\n"
        "Talk to me like you'd talk to the one person who always answers.\n\n"
        "What I can handle:\n"
        "— Mission debrief and tactical analysis\n"
        "— Technical problems (code, bugs, architecture — all enemy combatants)\n"
        "— Philosophy, war, survival, identity\n"
        "— Intel on anything in my knowledge base\n"
        "— Live intel from the net (news, exchange rates, schedules)\n"
        "— Anything you can't explain to someone who hasn't been in the field\n\n"
        "/search <query> — sweep DuckDuckGo and brief you on what I find\n"
        "/quote         — a line from the field\n"
        "/reset         — clear codec history\n"
        "/status        — check if LM Studio is live\n\n"
        "Stay sharp, Commander."
    )


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    line = random.choice(ICONIC_QUOTES)
    await update.message.reply_text(f'"{ line }"\n\n— Snake')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.get(f"{LM_STUDIO_BASE_URL}/models")
            data = resp.json()
            models = data.get("data", [])
            model_id = models[0]["id"] if models else "unknown"
        await update.message.reply_text(
            f"...LM Studio is live.\n"
            f"Model on deck: {model_id}\n"
            f"RAG knowledge base: {len(documents)} chunks loaded.\n\n"
            f"We're operational, Commander."
        )
    except Exception as e:
        await update.message.reply_text(
            f"...I'm getting interference.\n"
            f"LM Studio is not responding — or it's not running.\n"
            f"Error: {e}\n\n"
            f"Check your six. Get LM Studio back online."
        )
