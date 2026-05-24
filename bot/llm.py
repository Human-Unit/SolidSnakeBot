"""LM Studio client — model detection, request dispatch, response parsing."""

import re
import logging

import httpx
from openai import AsyncOpenAI

from bot.config import (
    LM_STUDIO_BASE_URL,
    LM_STUDIO_API_KEY,
    MODEL_NAME_FALLBACK,
    SYSTEM_PROMPT,
    MAX_TOKENS,
    TEMPERATURE,
    TOP_P,
    FREQUENCY_PENALTY,
)

logger = logging.getLogger(__name__)

# ─── Client ──────────────────────────────────────────────────────
client = AsyncOpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key=LM_STUDIO_API_KEY,
)

MODEL_NAME: str = MODEL_NAME_FALLBACK


async def detect_model() -> str:
    """Query LM Studio for the currently loaded model and update MODEL_NAME."""
    global MODEL_NAME
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{LM_STUDIO_BASE_URL}/models")
            data = resp.json()
            models = data.get("data", [])
            if models:
                detected = models[0]["id"]
                logger.info("LM Studio model detected: %s", detected)
                MODEL_NAME = detected
                return detected
    except Exception as e:
        logger.warning("LM Studio unreachable: %s", e)
    logger.warning("Using fallback MODEL_NAME: %s", MODEL_NAME)
    return MODEL_NAME


def _extract_reply(msg) -> str:
    """Extract usable text from an LLM response message, handling Qwen3 thinking mode."""
    raw = msg.content or ""

    # Qwen3 thinking mode: content may be empty while reasoning_content has the output
    if not raw.strip():
        extra = getattr(msg, "model_extra", {}) or {}
        reasoning = getattr(msg, "reasoning_content", None) or extra.get("reasoning_content", "")
        if reasoning.strip():
            logger.info("Using reasoning_content as reply (content was empty)")
            raw = reasoning

    # Strip any leftover <think>...</think> tags
    return re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", raw).strip()


async def generate_reply(
    messages: list[dict],
    *,
    max_tokens: int | None = None,
) -> str:
    """Send messages to LM Studio and return the parsed reply text."""
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=max_tokens or MAX_TOKENS,
        frequency_penalty=FREQUENCY_PENALTY,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return _extract_reply(response.choices[0].message)
