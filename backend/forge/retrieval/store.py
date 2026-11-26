"""Persist chunks + vectors for one agent (plain NumPy; small, portable, ships in the repo and on Render)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from forge.retrieval.bm25 import BM25Index
from forge.retrieval.embedder import Embedder
from forge.schemas.corpus import Chunk
from forge.util import read_jsonl, write_jsonl


class VectorStore:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray):
        self.chunks = chunks
        self.vectors = vectors.astype(np.float32) if len(chunks) else np.zeros((0, 1), dtype=np.float32)
        self.by_id = {c.chunk_id: c for c in chunks}
        self.pos = {c.chunk_id: i for i, c in enumerate(chunks)}

    def search(self, query_vec: np.ndarray, k: int = 30) -> list[tuple[str, float]]:
        if not self.chunks:
            return []
        sims = self.vectors @ query_vec
        order = np.argsort(-sims)[:k]
        return [(self.chunks[i].chunk_id, float(sims[i])) for i in order]

    def get(self, chunk_id: str) -> Chunk | None:
        return self.by_id.get(chunk_id)


def corpus_sha(chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(c.text.encode())
    return h.hexdigest()[:16]


def build_index(chunks: list[Chunk], embedder: Embedder, index_dir: Path, chunk_size: int,
                overlap: int, docs_sha: str = "") -> tuple[VectorStore, BM25Index]:
    index_dir.mkdir(parents=True, exist_ok=True)
    vectors = embedder.embed_documents([c.embed_text() for c in chunks])
    store = VectorStore(chunks, vectors)
    bm25 = BM25Index.build([c.chunk_id for c in chunks], [c.embed_text() for c in chunks])
    np.save(index_dir / "vectors.npy", store.vectors)
    write_jsonl(index_dir / "chunks.jsonl", chunks)
    bm25.save(index_dir / "bm25.json")
    manifest = {"embedder": embedder.name, "chunk_size": chunk_size, "overlap": overlap, "n_chunks": len(chunks),
                "corpus_sha": corpus_sha(chunks), "docs_sha": docs_sha}
    (index_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return store, bm25


def load_index(index_dir: Path) -> tuple[VectorStore, BM25Index, dict]:
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    chunks = read_jsonl(index_dir / "chunks.jsonl", Chunk)
    vectors = np.load(index_dir / "vectors.npy") if chunks else np.zeros((0, 1), dtype=np.float32)
    return VectorStore(chunks, vectors), BM25Index.load(index_dir / "bm25.json"), manifest


def index_matches(index_dir: Path, embedder_name: str, chunk_size: int, overlap: int, docs_sha: str | None = None) -> bool:
    mf = index_dir / "manifest.json"
    if not mf.exists():
        return False
    m = json.loads(mf.read_text(encoding="utf-8"))
    ok = m.get("embedder") == embedder_name and m.get("chunk_size") == chunk_size and m.get("overlap") == overlap
    if docs_sha is not None:
        ok = ok and m.get("docs_sha") == docs_sha
    return ok
