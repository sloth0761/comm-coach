"""
core/embedder.py

Stage 4a helper — semantic embeddings (v1.5).
Wraps sentence-transformers. Loads model, encodes, frees. Never co-resident
with the coaching LLM (same load-use-free discipline as transcriber/analyzer).
"""
from __future__ import annotations

import gc
import logging

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding fails to load or encode."""


class Embedder:
    """Wraps sentence-transformers. Loads model, encodes, frees. Never co-resident with LLM."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name

    def embed(self, text: str) -> np.ndarray:
        return self._encode([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def _encode(self, texts: list[str]) -> np.ndarray:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise EmbeddingError("sentence-transformers not installed: pip install sentence-transformers") from e

        model = None
        try:
            model = SentenceTransformer(self.model_name)
            vecs  = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.array(vecs, dtype=np.float32)
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(str(e)) from e
        finally:
            if model is not None:
                del model
                gc.collect()
