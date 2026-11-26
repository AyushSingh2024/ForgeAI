"""Keyword retrieval: catches part numbers, clause ids and codes that embeddings miss."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

_CODE = re.compile(r"[A-Za-z0-9]+(?:[-_./&][A-Za-z0-9]+)+")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of to in on for and or is are was were be by with at as it this that from what which how "
            "do does can i my me we you your our".split())


def tokenize(text: str) -> list[str]:
    """Words plus whole code-like tokens ("MBW-6S50-INJ-0042", "3.2.1") kept intact."""
    low = text.lower()
    words = [w for w in _WORD.findall(low) if w not in _STOP]
    codes = [c.lower() for c in _CODE.findall(text)]
    return words + codes


class BM25Index:
    def __init__(self, chunk_ids: list[str], tokenized: list[list[str]]):
        self.chunk_ids = chunk_ids
        self.tokenized = tokenized
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    @classmethod
    def build(cls, chunk_ids: list[str], texts: list[str]) -> "BM25Index":
        return cls(chunk_ids, [tokenize(t) or ["_empty_"] for t in texts])

    def search(self, query: str, k: int = 30) -> list[tuple[str, float]]:
        if self._bm25 is None:
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(self.chunk_ids[i], float(scores[i])) for i in order if scores[i] > 0]

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"ids": self.chunk_ids, "tok": self.tokenized}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["ids"], d["tok"])
