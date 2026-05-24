"""Typing indicator helper."""

import asyncio
import logging

from telegram.constants import ChatAction

logger = logging.getLogger(__name__)


async def keep_typing(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    """Send 'typing...' action every 4 s until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass
