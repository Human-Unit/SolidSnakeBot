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
        if cut != -1:
            cut += 2
        else:
            cut = text.rfind("\n", 0, limit)
            if cut != -1:
                cut += 1
            else:
                cut = limit
        parts.append(text[:cut])
        text = text[cut:]
    if text:
        parts.append(text)
    return parts
