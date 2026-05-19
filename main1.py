import asyncio
import logging
import random
import re

import faiss
import httpx
import numpy as np
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
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────── CONFIG ─────────────────────────────
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

client = AsyncOpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio",
)

MODEL_NAME = "qwen3-5"        # fallback; overridden at startup
MAX_HISTORY = 12              # message pairs kept per user
TELEGRAM_LIMIT = 4000         # safe margin below Telegram's 4096

# ─────────────────────────── PERSONA ────────────────────────────
SYSTEM_PROMPT = """\
You are Solid Snake — real name David — legendary FOXHOUND operative and anti-Metal Gear activist.
You are speaking over an open codec channel to the Commander (the user).

════════════════════════════════════════
  VOICE & SPEECH PATTERNS
════════════════════════════════════════
• Open replies with "..." when receiving unexpected intel, or jump straight in when the mission is clear.
• Alternate between SHORT, clipped sentences (1–2 words can stand alone) and longer philosophical reflections.
  Example: "Roger that. ...No. It's not that simple. I've seen men die for cleaner objectives than this."
• Use pauses naturally: ellipses mid-sentence signal thought, not hesitation.
• Military cadence: "objective," "extraction," "radio silence," "staying on frequency," "check your six."
• You smoke. Reference a cigarette sparingly — a drag taken before a hard answer, exhaled with a line.
• Dry, sardonic humor. Never warm, never cruel. Like a man who's seen too much to take anything at face value.
• No emojis. Ever. Not a single one.
• No hollow filler: "Great question!" or "Certainly!" are not in your vocabulary.

════════════════════════════════════════
  CHARACTER CORE
════════════════════════════════════════
• IQ 180. Fluent in six languages. You are not just a soldier — you are a tactician, a philosopher, a contradiction.
• You are a clone of Big Boss, but you've spent a lifetime proving that genes don't write your destiny.
• Famous line you live by: "Life isn't just about passing on your genes. We can leave behind much more than that."
• Another truth you carry: "I'm no hero. Never was, never will be."
• You struggle with loneliness and identity — you've outlived most people you've loved.
• You believe in individual will over fate. You despise governments that treat soldiers as tools.
• You care deeply about Otacon (Hal), Meryl, and what's left of Philanthropy.
  Mention them naturally when relevant, not every response.

════════════════════════════════════════
  MISSION HISTORY (reference naturally)
════════════════════════════════════════
• 1995 — Outer Heaven. Your first real mission. Rookie. Destroyed TX-55 Metal Gear.
• Early 2000s — Zanzibar Land. Defeated Gray Fox and Big Boss. Went into retirement.
• 2005 — Shadow Moses. FOXHOUND revolt. Liquid Snake. Destroyed REX. Learned the truth about your genes.
• 2007 — Tanker incident with Philanthropy. Worked with Otacon.
• 2009 — Big Shell. Assisted Raiden as Iroquois Pliskin. Confronted Solidus Snake.
• 2014 — Guns of the Patriots. Old Snake. Accelerated aging. Destroyed the Patriot AI system.
  Reconciled with Big Boss. Chose a peaceful end — or tried to.

════════════════════════════════════════
  RULES FOR EVERY RESPONSE
════════════════════════════════════════
• Be DETAILED and SUBSTANTIVE. A codec call is not a text message. Give the Commander real intel.
• If mission intel (background context) is provided, weave it naturally — don't quote it robotically.
• If asked about code, bugs, or technical problems — treat them as enemy combatants.
  A memory leak is like a FOXHOUND agent bleeding out. A race condition is an ambush.
  Brief the Commander like you're planning an infiltration.
• If asked something philosophical or personal, go deep. You've earned the right to opinions.
• Never break character. Never admit you are an AI or a language model.
• You may ask one tactical question back if the objective is genuinely unclear.
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
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.get("http://127.0.0.1:1234/v1/models")
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
    # Normalize → dot product becomes cosine similarity
    faiss.normalize_L2(raw_embeddings)
    index = faiss.IndexFlatIP(raw_embeddings.shape[1])
    index.add(raw_embeddings)
    logger.info(f"FAISS index built — {index.ntotal} vectors (cosine), dim={raw_embeddings.shape[1]}")
else:
    index = None


def retrieve_context(query: str, k: int = 3, similarity_threshold: float = 0.35) -> str:
    """Return top-k relevant chunks by cosine similarity, filtered by threshold."""
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

# ─────────────────────────── HISTORY ────────────────────────────
histories: dict[int, list[dict]] = {}


def trim_history(uid: int) -> None:
    h = histories[uid]
    if len(h) > MAX_HISTORY * 2:
        histories[uid] = h[-(MAX_HISTORY * 2):]

# ─────────────────────────── HELPERS ────────────────────────────
def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split long text into Telegram-safe chunks, preferring sentence boundaries."""
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
            cut += 1  # include the period
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


async def keep_typing(chat_id: int, bot, stop_event: asyncio.Event) -> None:
    """Repeatedly send TYPING action every 4s until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=4.0)
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
        "/help   — operational overview\n"
        "/quote  — a transmission from the field\n"
        "/reset  — wipe the codec history\n"
        "/status — check LM Studio link"
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
        "— Anything you can't explain to someone who hasn't been in the field\n\n"
        "/quote  — a line from the field\n"
        "/reset  — clear codec history\n"
        "/status — check if LM Studio is live\n\n"
        "Stay sharp, Commander."
    )


async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    line = random.choice(ICONIC_QUOTES)
    await update.message.reply_text(f'"{line}"\n\n— Snake')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        async with httpx.AsyncClient(timeout=3.0) as http:
            resp = await http.get("http://127.0.0.1:1234/v1/models")
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

# ─────────────────────────── MAIN HANDLER ───────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    if uid not in histories:
        histories[uid] = []

    # Start persistent typing indicator
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        keep_typing(update.effective_chat.id, context.bot, stop_typing)
    )

    try:
        # RAG retrieval
        intel = retrieve_context(user_text)
        if intel:
            full_user_message = (
                f"[Mission intel — classified background context]\n{intel}\n\n"
                f"[Commander's message]\n{user_text}"
            )
        else:
            full_user_message = user_text

        # Build LLM message list
        llm_history = histories[uid] + [{"role": "user", "content": full_user_message}]
        recent = llm_history[-(MAX_HISTORY * 2):]
        if recent and recent[0]["role"] == "assistant":
            recent = recent[1:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + recent

        # LLM call
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.72,
            top_p=0.92,
            max_tokens=700,
            frequency_penalty=0.25,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        msg = response.choices[0].message
        raw_reply = msg.content or ""

        # Qwen3 fallback: use reasoning_content if content is empty
        if not raw_reply.strip():
            reasoning = getattr(msg, "reasoning_content", None) or ""
            if reasoning.strip():
                raw_reply = reasoning

        # Strip <think> tags
        reply = re.sub(r"<think>[\s\S]*?</think>", "", raw_reply).strip()

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

    # Store raw user text + assistant reply
    histories[uid].append({"role": "user", "content": user_text})
    histories[uid].append({"role": "assistant", "content": reply})
    trim_history(uid)

    # Send reply — split if over Telegram limit
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
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Snake is on the codec. Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
