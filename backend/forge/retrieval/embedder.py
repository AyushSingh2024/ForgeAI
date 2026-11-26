"""Text -> normalised vectors.

Backends: fastembed (ONNX, default, fits Render free), sentence-transformers (local extra), and a tiny
deterministic hashing embedder ("hash") used by tests and as a last-resort fallback when no model can load.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from functools import lru_cache

import numpy as np

log = logging.getLogger(__name__)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self.backend = "hash"
        self._model = None
        self._lock = threading.Lock()
        if model_name != "hash":
            self._load()

    def _load(self) -> None:
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
            self.backend = "fastembed"
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("fastembed unavailable (%s); trying sentence-transformers", exc)
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self.backend = "sentence-transformers"
        except Exception as exc:  # noqa: BLE001
            log.warning("no embedding model could load (%s); using hashing embedder", exc)
            self.backend = "hash"

    @property
    def name(self) -> str:
        return self.model_name if self.backend != "hash" else "hash"

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        with self._lock:
            if self.backend == "fastembed":
                vecs = np.array(list(self._model.embed(texts, batch_size=64)), dtype=np.float32)
            elif self.backend == "sentence-transformers":
                vecs = np.asarray(self._model.encode(texts, batch_size=64, normalize_embeddings=True),
                                  dtype=np.float32)
            else:
                vecs = np.stack([_hash_vec(t) for t in texts])
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_query(self, text: str) -> np.ndarray:
        prefix = BGE_QUERY_PREFIX if "bge" in self.model_name.lower() and self.backend != "hash" else ""
        return self._encode([prefix + text])[0]


_TOKEN = re.compile(r"[a-z0-9]+")


def _hash_vec(text: str, dim: int = 384) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    toks = _TOKEN.findall(text.lower())
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    for g in grams:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    return v


@lru_cache(maxsize=4)
def get_embedder(model_name: str) -> Embedder:
    return Embedder(model_name)
