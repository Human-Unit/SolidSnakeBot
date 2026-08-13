"""Central configuration - loads .env and exposes all settings."""

import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared in requirements.txt.
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
LM_STUDIO_BASE_URL: str = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LM_STUDIO_API_KEY: str = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
MODEL_NAME_FALLBACK: str = os.getenv("MODEL_NAME_FALLBACK", "gemma-4-e4b-it")

MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "12"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1200"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.72"))
TOP_P: float = float(os.getenv("TOP_P", "0.92"))
FREQUENCY_PENALTY: float = float(os.getenv("FREQUENCY_PENALTY", "0.25"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

PROMPT_FILE: Path = _project_path(os.getenv("PROMPT_FILE", "prompts/solid_snake.txt"))
KNOWLEDGE_BASE: Path = _project_path(os.getenv("KNOWLEDGE_BASE", "notes.txt"))

WEB_SEARCH_RESULTS: int = int(os.getenv("WEB_SEARCH_RESULTS", "5"))
WEB_PAGE_CHARS: int = int(os.getenv("WEB_PAGE_CHARS", "3000"))
TELEGRAM_MSG_LIMIT: int = int(os.getenv("TELEGRAM_MSG_LIMIT", "4000"))

logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger("bot")


def load_prompt() -> str:
    """Read the system prompt from the prompt file."""
    try:
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.error("Prompt file not found: %s", PROMPT_FILE)
        return "You are Solid Snake. Stay in character."


SYSTEM_PROMPT: str = load_prompt()

if not TELEGRAM_BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN is not set! Add it to .env")
    sys.exit(1)
