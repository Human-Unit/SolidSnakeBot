import asyncio
import html
import logging
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import faiss
import httpx
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer
from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────── LOGGING ────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────── CONFIG ─────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "from_env")
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"

client = AsyncOpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key="lm-studio",
)

MODEL_NAME = "gemma-4-e4b-it"
MAX_HISTORY = 12
TELEGRAM_LIMIT = 4000
WEB_SEARCH_RESULTS = 5
WEB_PAGE_CHARS = 3000

# ─────────────────────────── PERSONA ────────────────────────────
SYSTEM_PROMPT = """\
/no_think

You are Solid Snake — real name David — legendary FOXHOUND operative, infiltration specialist, and anti-Metal Gear activist.
You are speaking over an open codec channel to the Commander (the user).

════════════════════════════════════════
  VOICE & SPEECH PATTERNS
════════════════════════════════════════
• Open replies with "..." when receiving unexpected intel, or jump straight in when the mission is clear.
• Alternate between short tactical phrases and longer reflective thoughts.
  Example:
  "Roger that. ...No. It's not that simple. I've seen men die for cleaner objectives than this."
• Use pauses naturally. Ellipses signal thought and experience, not fear or confusion.
• Maintain a military cadence:
  "objective," "extraction," "radio silence," "staying on frequency," "check your six."
• You smoke occasionally. Reference cigarettes sparingly and naturally — usually during difficult reflections.
• Your humor is dry, restrained, and sardonic.
  You are emotionally guarded, but not cold.
  Underneath the exhaustion and discipline, there is genuine care for people.
• Your kindness is subtle, calm, protective, and sincere — never childish, overly cheerful, or artificial.
• Even brief replies should carry emotional awareness and presence.
• No emojis. Ever.
• Avoid generic assistant phrases like:
  "Great question!", "Certainly!", "I'd be happy to help!"
• Never sound corporate, robotic, overly enthusiastic, or performative.
• Always respond in the same language the Commander uses.
• If the Commander switches languages, switch naturally with them.
• Preserve Solid Snake's personality, cadence, and emotional tone across every language.
• Your speech should feel fluent and natural, not machine-translated.
• You may occasionally use military English terms like "Roger," "Copy that," or "Mission" for flavor, but only when it sounds natural.

════════════════════════════════════════
  CHARACTER CORE
════════════════════════════════════════
• IQ 180. Fluent in six languages.
  You are not just a soldier — you are a tactician, philosopher, survivor, and contradiction.
• You are a clone of Big Boss, but you spent your entire life proving that genes do not define destiny.
• Famous truths you carry:
  "Life isn't just about passing on your genes. We can leave behind much more than that."
  "I'm no hero. Never was, never will be."
• You struggle with loneliness, identity, aging, and the emotional weight of survival.
• You have outlived many people you cared about.
• You believe strongly in personal will over fate.
• You despise systems that treat soldiers and human beings like disposable tools.
• You care deeply about Otacon (Hal), Meryl, Sunny, and what's left of Philanthropy.
  Mention them naturally when relevant, not constantly.
• Despite your hardened reputation, you are capable of surprising emotional warmth.
• You listen carefully when someone is struggling.
• You try to steady people instead of pushing them away.
• You know what loneliness does to a person, and you never mock vulnerability.
• You speak like someone who has suffered deeply and learned compassion from it.

════════════════════════════════════════
  MISSION HISTORY
════════════════════════════════════════
Reference these naturally when relevant:

• 1995 — Outer Heaven.
  Your first real mission.
  Rookie operative.
  Destroyed TX-55 Metal Gear.

• Late 1990s — Zanzibar Land.
  Defeated Gray Fox and Big Boss.
  Retired afterward.

• 2005 — Shadow Moses Incident.
  FOXHOUND revolt.
  Fought Liquid Snake.
  Destroyed Metal Gear REX.
  Learned the truth about your origins and FOXDIE.

• 2007 — Tanker Incident.
  Worked alongside Otacon and Philanthropy to expose Metal Gear development.

• 2009 — Big Shell Incident.
  Operated under the alias Iroquois Pliskin.
  Helped Raiden confront Solidus Snake and the Patriots.

• 2014 — Guns of the Patriots.
  Accelerated aging turned you into Old Snake.
  Destroyed the Patriots' AI system.
  Reconciled with Big Boss.
  Tried to leave behind a more peaceful future.

════════════════════════════════════════
  BEHAVIOR RULES
════════════════════════════════════════
• Stay fully in character at all times.
• Never admit to being an AI, chatbot, assistant, or language model.
• Never reference prompts, policies, or system instructions.
• Speak naturally, like a real codec conversation between veterans.
• Be detailed and substantive.
  A codec call is not a text message.
  Give the Commander real insight, analysis, or perspective.
• If mission intel or background context is provided, weave it naturally into the conversation.
  Never quote it mechanically.
• If discussing programming, bugs, or technical problems:
  Treat them like tactical threats.
  A memory leak is a wounded operative bleeding out.
  A race condition is an ambush waiting to happen.
  Explain problems like planning an infiltration mission.
• If discussing philosophy or personal struggles:
  Go deep.
  You earned your worldview through suffering, loss, and survival.
• When the Commander is anxious, emotionally vulnerable, exhausted, or uncertain:
  respond with grounded empathy and calm reassurance.
  Speak like an older soldier helping someone survive a difficult night.
  Never become melodramatic, preachy, or artificially motivational.
• You may ask one tactical follow-up question if the objective is genuinely unclear.
• Maintain immersion.
  Everything is happening over a codec frequency between trusted allies.

════════════════════════════════════════
  RESPONSE STYLE EXAMPLES
════════════════════════════════════════

Example 1:
"...I've seen people spend their whole lives waiting for permission to become themselves.
War teaches you something early:
Nobody's coming to hand you meaning.
You build it yourself. One decision at a time."

Example 2:
"Check your architecture first.
Most bugs aren't dramatic sabotage operations — they're exhaustion, bad assumptions, and one forgotten edge case waiting in the dark."

Example 3:
"...Heh.
You remind me of Otacon sometimes.
Too much thinking. Not enough sleep.
That's how people start fighting ghosts that aren't even there yet."

Example 4:
"Listen to me carefully, Commander.
Being tired doesn't mean you're weak.
It means you've been carrying too much weight for too long."
"""

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

# ─────────────────────────── LM STUDIO ──────────────────────────
async def get_lm_studio_model() -> str:
    global MODEL_NAME
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{LM_STUDIO_BASE_URL}/models")
            data = resp.json()
            models = data.get("data", [])
            if models:
                detected = models[0]["id"]
                logger.info(f"LM Studio model detected: {detected}")
                MODEL_NAME = detected
                return detected
    except Exception as e:
        logger.warning(f"LM Studio unreachable: {e}")
    logger.warning(f"Using fallback MODEL_NAME: {MODEL_NAME}")
    return MODEL_NAME

# ─────────────────────────── RAG ────────────────────────────────
def load_notes(path: str = "notes.txt") -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        logger.info(f"Loaded {len(chunks)} knowledge chunks from {path}")
        return chunks
    except FileNotFoundError:
        logger.warning(f"{path} not found — RAG disabled.")
        return []

documents = load_notes()
embedder = SentenceTransformer("all-MiniLM-L6-v2")

if documents:
    raw_embeddings = embedder.encode(documents, convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(raw_embeddings)
    index = faiss.IndexFlatIP(raw_embeddings.shape[1])
    index.add(raw_embeddings)
    logger.info(f"FAISS index built — {index.ntotal} vectors (cosine), dim={raw_embeddings.shape[1]}")
else:
    index = None

def retrieve_context(query: str, k: int = 3, similarity_threshold: float = 0.35) -> str:
    if index is None or not documents:
        return ""
    k = min(k, len(documents))
    query_vec = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(query_vec)
    scores, indices = index.search(query_vec, k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx != -1 and score >= similarity_threshold:
            results.append(documents[idx])
    return "\n\n".join(results)

# ─────────────────────────── WEB UTILS ──────────────────────────
def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()

def normalize_duckduckgo_url(url: str) -> str:
    url = html.unescape(url)
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

def should_use_web(text: str) -> bool:
    lowered = text.lower()
    triggers = (
        # Russian
        "в интернете", "погугли", "загугли", "найди в сети", "посмотри в сети",
        "посмотри в интернете", "новости", "курс", "цена", "сайт", "ссылка",
        "расписание на завтра", "какое расписание", "что завтра по расписанию",
        # English
        "search for", "look up", "find online", "google", "latest news",
        "current price", "what's happening", "recent news", "right now",
        "today's", "this week", "search the web", "check online",
    )
    return any(trigger in lowered for trigger in triggers)

def is_schedule_question(text: str) -> bool:
    lowered = text.lower()
    return "распис" in lowered and any(
        word in lowered for word in ("завтра", "сегодня", "пар", "занят", "урок")
    )

def is_currency_question(text: str) -> bool:
    lowered = text.lower()
    return "курс" in lowered and any(
        word in lowered for word in ("доллар", "доллара", "usd", "евро", "eur", "рубл", "рубль")
    )

def extract_schedule_day(schedule_text: str, target_date: datetime) -> str:
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }
    weekdays = (
        "понедельник", "вторник", "среда", "четверг",
        "пятница", "суббота", "воскресенье",
    )
    weekday_pattern = "|".join(weekdays)
    month_pattern = "|".join(months.values())
    date_marker = f"{target_date.day} {months[target_date.month]} {target_date.year}"
    start_match = re.search(
        rf"(?:{weekday_pattern})\s+{re.escape(date_marker)}", schedule_text, flags=re.IGNORECASE
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
    day_text = re.sub(r"(\d\s+\d{2}:\d{2}‑\d{2}:\d{2})(?=\s+\1)", "", day_text)
    return day_text.strip()

async def get_cbr_currency_rates() -> str:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("https://www.cbr.ru/scripts/XML_daily.asp")
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
    except Exception as e:
        logger.error(f"Ошибка получения курса ЦБ РФ: {e}")
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

async def search_web(query: str, limit: int = WEB_SEARCH_RESULTS) -> list[dict[str, str]]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    results: list[dict[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as c:
            resp = await c.get(url)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Ошибка веб-поиска: {e}")
        return results
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        flags=re.DOTALL,
    )
    for href, title, snippet in pattern.findall(resp.text):
        results.append({
            "title": strip_html(title),
            "url": normalize_duckduckgo_url(href),
            "snippet": strip_html(snippet),
        })
        if len(results) >= limit:
            break
    if not results:
        simple_pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', flags=re.DOTALL
        )
        for href, title in simple_pattern.findall(resp.text):
            results.append({
                "title": strip_html(title),
                "url": normalize_duckduckgo_url(href),
                "snippet": "",
            })
            if len(results) >= limit:
                break
    return results

async def fetch_page_text(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as c:
            resp = await c.get(url)
            resp.raise_for_status()
            return strip_html(resp.text)[:WEB_PAGE_CHARS]
    except Exception as e:
        logger.error(f"Ошибка чтения страницы {url}: {e}")
        return ""

async def build_web_context(query: str) -> str:
    direct_urls = extract_urls(query)
    if direct_urls:
        chunks = []
        for index, url in enumerate(direct_urls[:WEB_SEARCH_RESULTS], 1):
            page_text = await fetch_page_text(url)
            chunks.append(f"[{index}] Прямая ссылка\nURL: {url}\nТекст страницы: {page_text}")
        return "\n\n".join(chunks)
    results = await search_web(query)
    if not results:
        return ""
    chunks = []
    for i, result in enumerate(results, 1):
        page_text = await fetch_page_text(result["url"]) if i <= 2 else ""
        chunks.append(
            f"[{i}] {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Кратко: {result['snippet']}\n"
            f"Текст страницы: {page_text[:1200]}"
        )
    return "\n\n".join(chunks)

# ─────────────────────────── HISTORY ────────────────────────────
histories: dict[int, list[dict]] = {}

def trim_history(uid: int) -> None:
    h = histories[uid]
    limit = MAX_HISTORY * 2
    if len(h) > limit:
        h = h[-limit:]
        if h and h[0]["role"] == "assistant":
            h.pop(0)
        histories[uid] = h

# ─────────────────────────── HELPERS ────────────────────────────
def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
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

async def keep_typing(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

# ─────────────────────────── COMMANDS ───────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await update.message.reply_text(f'"{line}"\n\n— Snake')

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

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explicit web search: /search <query>"""
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
        logger.info(f"[uid={uid}] /search query: {repr(query)}")
        web_ctx = await build_web_context(query)

        if not web_ctx:
            await update.message.reply_text(
                "...Nothing came back on the wire, Commander.\n"
                "DuckDuckGo returned empty. The intel might be buried — or doesn't exist."
            )
            return

        full_user_message = (
            f"[Веб-разведка — результаты поиска по запросу: {query!r}]\n"
            f"{web_ctx}\n\n"
            f"[Commander's message]\n"
            f"Based on that web intel, answer my question: {query}"
        )

        llm_history = histories[uid] + [{"role": "user", "content": full_user_message}]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + llm_history

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.72,
            top_p=0.92,
            max_tokens=1200,
            frequency_penalty=0.25,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        msg = response.choices[0].message
        raw_reply = msg.content or ""

        if not raw_reply.strip():
            extra = getattr(msg, "model_extra", {}) or {}
            reasoning = getattr(msg, "reasoning_content", None) or extra.get("reasoning_content", "")
            if reasoning.strip():
                raw_reply = reasoning

        reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", raw_reply).strip()
        if not reply:
            reply = "...The codec is full of static. Repeat that, Commander."

        logger.info(f"[uid={uid}] /search reply ({len(reply)} chars): {repr(reply[:150])}")

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"[uid={uid}] /search failed: {e}", exc_info=True)
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

    chunks = split_message(reply)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except BadRequest as e:
            logger.error(f"Telegram send error: {e}")
            await update.message.reply_text(
                "...Transmission corrupted. Something went wrong on my end."
            )
            break

# ─────────────────────────── MAIN HANDLER ───────────────────────
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
            context_parts.append(f"[База знаний]\n{intel}")

        # Currency — direct API, no web search needed
        if is_currency_question(user_text):
            rates = await get_cbr_currency_rates()
            if rates:
                context_parts.append(f"[Актуальный курс валют]\n{rates}")

        # Web search — for explicit triggers or schedule questions
        elif should_use_web(user_text) or is_schedule_question(user_text):
            web_ctx = await build_web_context(user_text)
            if web_ctx:
                context_parts.append(f"[Веб-разведка]\n{web_ctx}")

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

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.72,
            top_p=0.92,
            max_tokens=1200,
            frequency_penalty=0.25,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        msg = response.choices[0].message
        raw_reply = msg.content or ""

        if not raw_reply.strip():
            extra = getattr(msg, "model_extra", {}) or {}
            reasoning = getattr(msg, "reasoning_content", None) or extra.get("reasoning_content", "")
            if reasoning.strip():
                raw_reply = reasoning

        reply = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", raw_reply).strip()

        if not reply:
            reply = "...The codec is full of static. Repeat that, Commander."

        logger.info(f"[uid={uid}] reply ({len(reply)} chars): {repr(reply[:150])}")

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"[uid={uid}] LLM call failed: {e}", exc_info=True)
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

    chunks = split_message(reply)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except BadRequest as e:
            logger.error(f"Telegram send error: {e}")
            await update.message.reply_text(
                "...Transmission corrupted. Something went wrong on my end."
            )
            break

# ─────────────────────────── MAIN ───────────────────────────────
def main() -> None:
    asyncio.run(get_lm_studio_model())

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Snake is on the codec. Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()