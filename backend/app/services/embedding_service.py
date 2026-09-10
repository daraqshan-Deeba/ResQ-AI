"""Local text embeddings for Supabase pgvector search (384-dim MiniLM)."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("resq.embedding")

EMBEDDING_DIMENSIONS = 384
_MODEL_NAME = "BAAI/bge-small-en-v1.5"

_embedder = None
_embedding_available = False
_embedding_error: Optional[str] = None


def _init_embedder() -> None:
    global _embedder, _embedding_available, _embedding_error
    if _embedder is not None or _embedding_error is not None:
        return
    try:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=_MODEL_NAME)
        _embedding_available = True
        logger.info("Embedding model loaded: %s", _MODEL_NAME)
    except Exception as exc:
        _embedding_available = False
        _embedding_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Embedding model unavailable (%s). Vector search disabled.", type(exc).__name__)


def embedding_available() -> bool:
    _init_embedder()
    return _embedding_available


def embedding_error_detail() -> Optional[str]:
    _init_embedder()
    return _embedding_error


def embed_text(text: str) -> Optional[list[float]]:
    """Return a dense embedding vector, or None if the model is unavailable."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    _init_embedder()
    if not _embedding_available or _embedder is None:
        return None

    try:
        vectors = list(_embedder.embed([cleaned]))
        if not vectors:
            return None
        vector = vectors[0]
        return [float(v) for v in vector]
    except Exception as exc:
        logger.warning("embed_text failed: %s", exc)
        return None
