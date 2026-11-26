"""Optional cross-encoder reranker (an optimizer knob for retrieval misses). Never crashes: falls back to no-op."""

from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _load():
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        return TextCrossEncoder(model_name=RERANK_MODEL)
    except Exception as exc:  # noqa: BLE001
        log.warning("reranker unavailable (%s); rerank is a no-op", exc)
        return None


def rerank(query: str, hits: list, top_n: int = 20) -> list:
    model = _load()
    if model is None or not hits:
        return hits
    head, tail = hits[:top_n], hits[top_n:]
    try:
        scores = list(model.rerank(query, [h.chunk.text for h in head]))
    except Exception as exc:  # noqa: BLE001
        log.warning("rerank failed: %s", exc)
        return hits
    order = sorted(range(len(head)), key=lambda i: -scores[i])
    return [head[i] for i in order] + tail
