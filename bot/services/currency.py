"""CBR (Central Bank of Russia) currency rates."""

import logging
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)


def is_currency_question(text: str) -> bool:
    lowered = text.lower()
    return "курс" in lowered and any(
        w in lowered for w in ("доллар", "доллара", "usd", "евро", "eur", "рубл", "рубль")
    )


async def get_cbr_currency_rates() -> str:
    """Fetch current USD/EUR rates from the Central Bank of Russia."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            resp = await c.get("https://www.cbr.ru/scripts/XML_daily.asp")
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
    except Exception as e:
        logger.error("CBR currency fetch error: %s", e)
        return ""
    date = root.attrib.get("Date", "")
    wanted = {"USD": "доллар США", "EUR": "евро"}
    lines = [f"Курсы ЦБ РФ на {date}:"]
    for valute in root.findall("Valute"):
        char_code = valute.findtext("CharCode")
        if char_code in wanted:
            nominal = valute.findtext("Nominal", "1")
            value = valute.findtext("Value", "")
            lines.append(f"{nominal} {char_code} ({wanted[char_code]}) = {value} RUB")
    lines.append("Источник: https://www.cbr.ru/scripts/XML_daily.asp")
    return "\n".join(lines)
