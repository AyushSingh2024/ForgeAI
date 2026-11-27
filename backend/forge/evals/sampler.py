"""Choose WHICH chunks the cases are written about, so coverage is broad and reproducible."""

from __future__ import annotations

import random
from collections import defaultdict

import numpy as np

from forge.retrieval.embedder import Embedder
from forge.schemas.corpus import Chunk
from forge.util import parse_numbers


def usable(chunks: list[Chunk], min_tokens: int = 25) -> list[Chunk]:
    out = []
    for c in chunks:
        if c.chunk_id.startswith("table:") or c.token_count < min_tokens:
            continue
        words = c.text.split()
        if words and len(parse_numbers(c.text)) / len(words) > 0.5:  # mostly numbers: a table dump
            continue
        out.append(c)
    return out


def sample_single(chunks: list[Chunk], n: int, seed: int, exclude: set[str] | None = None) -> list[Chunk]:
    """Round-robin over documents so every document gets questions."""
    rng = random.Random(seed)
    exclude = exclude or set()
    by_doc: dict[str, list[Chunk]] = defaultdict(list)
    for c in usable(chunks):
        if c.chunk_id not in exclude:
            by_doc[c.doc_id].append(c)
    for lst in by_doc.values():
        rng.shuffle(lst)
    docs = sorted(by_doc)
    rng.shuffle(docs)
    out: list[Chunk] = []
    while len(out) < n and any(by_doc.values()):
        for d in docs:
            if by_doc[d] and len(out) < n:
                out.append(by_doc[d].pop())
    return out


def _vectors(chunks: list[Chunk], embedder: Embedder) -> np.ndarray:
    return embedder.embed_documents([c.embed_text() for c in chunks])


def sample_pairs(chunks: list[Chunk], n: int, embedder: Embedder, seed: int, same_doc: bool = False,
                 lo: float = 0.35, hi: float = 0.85) -> list[tuple[Chunk, Chunk]]:
    """Related chunk pairs: from different documents (multi_doc) or the same document (ambiguous)."""
    pool = usable(chunks)
    if len(pool) < 2:
        return []
    if len(pool) > 600:  # pair search is quadratic: sample very large corpora first
        pool = random.Random(seed).sample(pool, 600)
    vecs = _vectors(pool, embedder)
    sims = vecs @ vecs.T
    cands = []
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            if (pool[i].doc_id == pool[j].doc_id) != same_doc:
                continue
            if lo <= sims[i, j] <= hi:
                cands.append((float(sims[i, j]), i, j))
    if not cands:  # fall back to the most similar pairs available
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                if (pool[i].doc_id == pool[j].doc_id) == same_doc:
                    cands.append((float(sims[i, j]), i, j))
    cands.sort(reverse=True)
    rng = random.Random(seed)
    top = cands[: max(n * 4, n)]
    rng.shuffle(top)
    used: set[int] = set()
    out = []
    for _, i, j in top:
        if i in used or j in used:
            continue
        used |= {i, j}
        out.append((pool[i], pool[j]))
        if len(out) >= n:
            break
    return out
