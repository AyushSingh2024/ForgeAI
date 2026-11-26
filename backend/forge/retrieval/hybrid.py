"""Hybrid BM25 + dense retrieval with Reciprocal Rank Fusion, optional rerank and multi-query rewrite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from forge.retrieval.bm25 import BM25Index
from forge.retrieval.embedder import Embedder, get_embedder
from forge.retrieval.rerank import rerank as rerank_hits
from forge.retrieval.store import VectorStore, load_index
from forge.schemas.agent_def import RetrievalCfg
from forge.schemas.corpus import Chunk

RRF_K = 60
POOL = 30


@dataclass
class Hit:
    chunk: Chunk
    score: float
    dense_score: float
    bm25_score: float
    rank: int = 0

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id


class Rewrites(BaseModel):
    queries: list[str] = Field(default_factory=list)


class HybridRetriever:
    def __init__(self, store: VectorStore, bm25: BM25Index, embedder: Embedder, cfg: RetrievalCfg, llm=None):
        self.store = store
        self.bm25 = bm25
        self.embedder = embedder
        self.cfg = cfg
        self.llm = llm  # only needed for query_rewrite

    @classmethod
    def from_index(cls, index_dir: Path, cfg: RetrievalCfg, llm=None) -> "HybridRetriever":
        store, bm25, manifest = load_index(index_dir)
        return cls(store, bm25, get_embedder(manifest.get("embedder", cfg.embedder)), cfg, llm)

    def _one(self, query: str) -> dict[str, tuple[float, float, float]]:
        """chunk_id -> (rrf, dense, bm25) for one query string."""
        dense = self.store.search(self.embedder.embed_query(query), POOL) if self.cfg.mode != "bm25" else []
        sparse = self.bm25.search(query, POOL) if self.cfg.mode != "dense" else []
        w = self.cfg.bm25_weight if self.cfg.mode == "hybrid" else (1.0 if self.cfg.mode == "bm25" else 0.0)
        out: dict[str, list[float]] = {}
        for rank, (cid, s) in enumerate(dense):
            e = out.setdefault(cid, [0.0, s, 0.0])
            e[0] += (1 - w) / (RRF_K + rank + 1)
            e[1] = s
        for rank, (cid, s) in enumerate(sparse):
            e = out.setdefault(cid, [0.0, 0.0, s])
            e[0] += w / (RRF_K + rank + 1)
            e[2] = s
        # dense similarity for chunks only found by BM25 (needed for the refuse threshold)
        if sparse and self.cfg.mode != "bm25":
            qv = self.embedder.embed_query(query)
            for cid, e in out.items():
                if e[1] == 0.0:
                    idx = self.store.pos.get(cid)
                    if idx is not None:
                        e[1] = float(self.store.vectors[idx] @ qv)
        return {k: (v[0], v[1], v[2]) for k, v in out.items()}

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        k = k or self.cfg.top_k
        queries = [query]
        if self.cfg.query_rewrite and self.llm is not None:
            res = self.llm.complete("query_rewrite", {"query": query}, schema=Rewrites, max_tokens=200)
            if res.ok:
                queries += [q for q in res.data.queries[:2] if q.strip()]
        fused: dict[str, list[float]] = {}
        for q in queries:
            for cid, (rrf, d, b) in self._one(q).items():
                e = fused.setdefault(cid, [0.0, d, b])
                e[0] += rrf
                e[1], e[2] = max(e[1], d), max(e[2], b)
        ranked = sorted(fused.items(), key=lambda kv: -kv[1][0])
        hits = [Hit(chunk=self.store.by_id[cid], score=v[0], dense_score=v[1], bm25_score=v[2])
                for cid, v in ranked if cid in self.store.by_id]
        if self.cfg.rerank:
            hits = rerank_hits(query, hits)
        hits = hits[:k]
        for i, h in enumerate(hits):
            h.rank = i + 1
        return hits

    @staticmethod
    def best_score(hits: list[Hit]) -> float:
        return max((h.dense_score for h in hits), default=0.0)
