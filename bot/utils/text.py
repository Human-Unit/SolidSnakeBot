"""Text processing utilities."""

import html
import re

from bot.config import TELEGRAM_MSG_LIMIT


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()


def split_message(text: str, limit: int = TELEGRAM_MSG_LIMIT) -> list[str]:
    """Split a long message into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind(". ", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        else:
            cut += 1
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts
