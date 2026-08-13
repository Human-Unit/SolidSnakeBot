import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("KNOWLEDGE_BASE", "__missing_test_notes__.txt")


class RefactorTests(unittest.TestCase):
    def test_split_message_respects_limit_and_preserves_text(self):
        from bot.utils.text import split_message

        text = "Alpha. Beta. Gamma. Delta."
        parts = split_message(text, limit=12)

        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 12 for part in parts))
        self.assertEqual("".join(parts), text)

    def test_duckduckgo_redirect_is_unwrapped(self):
        from bot.services.web_search import normalize_duckduckgo_url

        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpath%3Fa%3D1"

        self.assertEqual(normalize_duckduckgo_url(url), "https://example.com/path?a=1")

    def test_web_and_currency_triggers_match_english_and_russian(self):
        from bot.services.currency import is_currency_question
        from bot.services.web_search import is_schedule_question, should_use_web

        self.assertTrue(should_use_web("look up recent news about LM Studio"))
        self.assertTrue(should_use_web("погугли новости про Python"))
        self.assertTrue(is_schedule_question("какое расписание на завтра?"))
        self.assertTrue(is_currency_question("какой курс доллара сегодня?"))
        self.assertTrue(is_currency_question("current курс USD"))

    def test_retrieve_context_returns_empty_without_knowledge_base(self):
        self._install_fake_rag_dependencies()

        import bot.config as config

        original = config.KNOWLEDGE_BASE
        config.KNOWLEDGE_BASE = Path("__missing_test_notes__.txt")
        sys.modules.pop("bot.rag", None)
        try:
            rag = importlib.import_module("bot.rag")
            self.assertEqual(rag.retrieve_context("anything"), "")
        finally:
            config.KNOWLEDGE_BASE = original

    def test_main_import_has_no_startup_side_effects(self):
        self._install_fake_rag_dependencies()
        sys.modules.pop("main", None)

        with patch("bot.llm.detect_model") as detect_model:
            imported = importlib.import_module("main")

        self.assertTrue(hasattr(imported, "build_application"))
        detect_model.assert_not_called()

    @staticmethod
    def _install_fake_rag_dependencies():
        fake_faiss = types.ModuleType("faiss")
        fake_faiss.normalize_L2 = lambda vectors: None

        class FakeIndex:
            def __init__(self, dimension):
                self.dimension = dimension
                self.ntotal = 0

            def add(self, vectors):
                self.ntotal = len(vectors)

            def search(self, query_vec, k):
                return [[0.0]], [[-1]]

        fake_faiss.IndexFlatIP = FakeIndex
        sys.modules.setdefault("faiss", fake_faiss)

        fake_sentence_transformers = types.ModuleType("sentence_transformers")

        class FakeSentenceTransformer:
            def __init__(self, model_name):
                self.model_name = model_name

            def encode(self, texts, convert_to_numpy=True):
                return []

        fake_sentence_transformers.SentenceTransformer = FakeSentenceTransformer
        sys.modules.setdefault("sentence_transformers", fake_sentence_transformers)


if __name__ == "__main__":
    unittest.main()
