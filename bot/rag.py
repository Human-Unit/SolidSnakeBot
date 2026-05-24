"""RAG — knowledge base loading, FAISS indexing, context retrieval."""

import logging

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from bot.config import KNOWLEDGE_BASE

logger = logging.getLogger(__name__)

# ─── Load notes ──────────────────────────────────────────────────
def load_notes() -> list[str]:
    """Read and chunk the knowledge base file."""
    try:
        text = KNOWLEDGE_BASE.read_text(encoding="utf-8")
        chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
        logger.info("Loaded %d knowledge chunks from %s", len(chunks), KNOWLEDGE_BASE)
        return chunks
    except FileNotFoundError:
        logger.warning("%s not found — RAG disabled.", KNOWLEDGE_BASE)
        return []


documents: list[str] = load_notes()

# ─── Embedding & Index ───────────────────────────────────────────
embedder = SentenceTransformer("all-MiniLM-L6-v2")

if documents:
    _raw = embedder.encode(documents, convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(_raw)
    index = faiss.IndexFlatIP(_raw.shape[1])
    index.add(_raw)
    logger.info("FAISS index built — %d vectors (cosine), dim=%d", index.ntotal, _raw.shape[1])
else:
    index = None
    logger.info("No documents — FAISS index not built.")


def retrieve_context(query: str, k: int = 3, threshold: float = 0.35) -> str:
    """Return the top-k relevant knowledge chunks, or empty string."""
    if index is None or not documents:
        return ""
    k = min(k, len(documents))
    q_vec = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_vec)
    scores, indices = index.search(q_vec, k)
    results = [
        documents[idx]
        for score, idx in zip(scores[0], indices[0])
        if idx != -1 and score >= threshold
    ]
    return "\n\n".join(results)
