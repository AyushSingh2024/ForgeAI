"""Hybrid retrieval with the offline hashing embedder."""

from __future__ import annotations

from forge.ingest.chunker import chunk_documents
from forge.ingest.loaders import load_folder
from forge.retrieval.bm25 import tokenize
from forge.retrieval.embedder import Embedder
from forge.retrieval.hybrid import HybridRetriever
from forge.retrieval.store import build_index, index_matches
from forge.schemas.agent_def import RetrievalCfg


def _retriever(tmp_path, tiny_corpus, **cfg):
    docs, _, _ = load_folder(tiny_corpus)
    chunks = chunk_documents(docs, 120, 20)
    emb = Embedder("hash")
    build_index(chunks, emb, tmp_path / "idx", 120, 20)
    return HybridRetriever.from_index(tmp_path / "idx", RetrievalCfg(embedder="hash", top_k=3, **cfg))


def test_tokenize_keeps_codes():
    toks = tokenize("Order part MBW-6S50-INJ-0042 per clause 3.2.1")
    assert "mbw-6s50-inj-0042" in toks and "3.2.1" in toks


def test_keyword_query_finds_right_chunk(tmp_path, tiny_corpus):
    r = _retriever(tmp_path, tiny_corpus)
    hits = r.search("administration fee for annual membership refund")
    assert hits and hits[0].chunk.doc_id == "refund_policy"


def test_deterministic_order(tmp_path, tiny_corpus):
    r = _retriever(tmp_path, tiny_corpus)
    a = [h.chunk_id for h in r.search("sauna closing time")]
    b = [h.chunk_id for h in r.search("sauna closing time")]
    assert a == b


def test_manifest_detects_stale_params(tmp_path, tiny_corpus):
    _retriever(tmp_path, tiny_corpus)
    assert index_matches(tmp_path / "idx", "hash", 120, 20)
    assert not index_matches(tmp_path / "idx", "hash", 300, 20)
