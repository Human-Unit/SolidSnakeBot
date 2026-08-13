"""DuckDuckGo web search, page fetching, and URL utilities."""

import html as html_mod
import logging
import re
from datetime import datetime
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from bot.config import WEB_PAGE_CHARS, WEB_SEARCH_RESULTS

logger = logging.getLogger(__name__)


def normalize_duckduckgo_url(url: str) -> str:
    url = html_mod.unescape(url)
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/"):
        url = "https://duckduckgo.com" + url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return unquote(params["uddg"][0])
    return url


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s<>)\"']+", text)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_mod.unescape(text)).strip()


def should_use_web(text: str) -> bool:
    lowered = text.lower()
    triggers = (
        "в интернете",
        "погугли",
        "загугли",
        "найди в сети",
        "посмотри в сети",
        "посмотри в интернете",
        "новости",
        "курс",
        "цена",
        "сайт",
        "ссылка",
        "расписание на завтра",
        "какое расписание",
        "что завтра по расписанию",
        "search for",
        "look up",
        "find online",
        "google",
        "latest news",
        "current price",
        "what's happening",
        "recent news",
        "right now",
        "today's",
        "this week",
        "search the web",
        "check online",
    )
    return any(trigger in lowered for trigger in triggers)


def is_schedule_question(text: str) -> bool:
    lowered = text.lower()
    return "распис" in lowered and any(
        word in lowered for word in ("завтра", "сегодня", "пар", "занят", "урок")
    )


def extract_schedule_day(schedule_text: str, target_date: datetime) -> str:
    months = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    weekdays = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    weekday_pattern = "|".join(weekdays)
    month_pattern = "|".join(months.values())
    date_marker = f"{target_date.day} {months[target_date.month]} {target_date.year}"
    start_match = re.search(
        rf"(?:{weekday_pattern})\s+{re.escape(date_marker)}",
        schedule_text,
        flags=re.IGNORECASE,
    )
    if not start_match:
        start_match = re.search(re.escape(date_marker), schedule_text, flags=re.IGNORECASE)
    if not start_match:
        return ""
    next_match = re.search(
        rf"\s(?:{weekday_pattern})\s+\d{{1,2}}\s+(?:{month_pattern})\s+\d{{4}}",
        schedule_text[start_match.end():],
        flags=re.IGNORECASE,
    )
    end = (
        start_match.end() + next_match.start()
        if next_match
        else min(len(schedule_text), start_match.start() + 1800)
    )
    day_text = schedule_text[start_match.start():end]
    day_text = re.sub(r"(\d\s+\d{2}:\d{2}[-‑]\d{2}:\d{2})(?=\s+\1)", "", day_text)
    return day_text.strip()


async def search_web(query: str, limit: int = WEB_SEARCH_RESULTS) -> list[dict[str, str]]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    results: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Web search error: %s", exc)
        return results

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        flags=re.DOTALL,
    )
    for href, title, snippet in pattern.findall(resp.text):
        results.append(
            {
                "title": strip_html(title),
                "url": normalize_duckduckgo_url(href),
                "snippet": strip_html(snippet),
            }
        )
        if len(results) >= limit:
            break

    if not results:
        simple_pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.DOTALL,
        )
        for href, title in simple_pattern.findall(resp.text):
            results.append(
                {
                    "title": strip_html(title),
                    "url": normalize_duckduckgo_url(href),
                    "snippet": "",
                }
            )
            if len(results) >= limit:
                break
    return results


async def fetch_page_text(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return strip_html(resp.text)[:WEB_PAGE_CHARS]
    except Exception as exc:
        logger.error("Page fetch error %s: %s", url, exc)
        return ""


async def build_web_context(query: str) -> str:
    direct_urls = extract_urls(query)
    if direct_urls:
        chunks = []
        for index, url in enumerate(direct_urls[:WEB_SEARCH_RESULTS], 1):
            page_text = await fetch_page_text(url)
            chunks.append(f"[{index}] Direct link\nURL: {url}\nPage text: {page_text}")
        return "\n\n".join(chunks)

    results = await search_web(query)
    if not results:
        return ""
    chunks = []
    for index, result in enumerate(results, 1):
        page_text = await fetch_page_text(result["url"]) if index <= 2 else ""
        chunks.append(
            f"[{index}] {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Summary: {result['snippet']}\n"
            f"Page text: {page_text[:1200]}"
        )
    return "\n\n".join(chunks)
