# SolidSnakeBot

Telegram bot that talks through a Solid Snake-style codec persona, uses LM Studio through an OpenAI-compatible API, can retrieve local notes with FAISS, and can fetch web or currency context for explicit requests.

## Features

- Solid Snake-style codec persona loaded from `prompts/solid_snake.txt`.
- Local LM Studio generation through the OpenAI-compatible `/v1` API.
- Reasoning-model cleanup for empty content or `<think>...</think>` responses.
- Optional RAG over `notes.txt` with `sentence-transformers` and FAISS.
- Explicit DuckDuckGo web search through `/search <query>`.
- Direct USD/EUR currency lookup from the Central Bank of Russia for currency questions.
- Rolling per-user conversation history.

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`.

4. Start LM Studio with an OpenAI-compatible server at `http://127.0.0.1:1234/v1`, or update `LM_STUDIO_BASE_URL` in `.env`.

5. Run the bot:

   ```powershell
   python main.py
   ```

## Configuration

All runtime settings are read from `.env` through `bot/config.py`.

- `TELEGRAM_BOT_TOKEN` is required.
- `PROMPT_FILE` defaults to `prompts/solid_snake.txt`.
- `KNOWLEDGE_BASE` defaults to `notes.txt`.
- `MODEL_NAME_FALLBACK`, generation settings, web-search limits, and Telegram message limits can be adjusted in `.env`.

## Commands

- `/start` opens a new codec session.
- `/help` shows the operational overview.
- `/reset` clears conversation history for the current user.
- `/quote` returns a Solid Snake quote.
- `/search <query>` runs explicit DuckDuckGo web search and asks the local model to brief the result.
- `/status` checks LM Studio and shows how many RAG chunks are loaded.

## Verification

Run syntax checks:

```powershell
python -m py_compile main.py bot\config.py bot\llm.py bot\rag.py bot\handlers\message.py bot\handlers\commands.py bot\handlers\search.py bot\services\web_search.py bot\services\currency.py bot\utils\text.py bot\utils\typing.py tests\test_refactor.py
```

Run the focused test suite:

```powershell
python -m unittest discover -s tests
```

## Disclaimer

This is a fan-made project. Solid Snake, Metal Gear, and related characters are properties of Konami. This software is provided as is, without warranty of any kind.
