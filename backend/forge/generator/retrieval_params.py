"""Initial retrieval settings from corpus statistics (rules, no LLM). Each choice carries its reason."""

from __future__ import annotations

from forge.config import ForgeConfig
from forge.schemas.agent_def import RetrievalCfg
from forge.schemas.corpus import CorpusProfile


def choose_retrieval(profile: CorpusProfile, cfg: ForgeConfig) -> RetrievalCfg:
    d = cfg.retrieval
    reasons = []
    med = profile.median_section_tokens
    if med and med < 250:
        size, overlap = 350, 50
        reasons.append(f"chunk_size 350: sections are short (median {med} tokens), FAQ-like")
    elif med > 900 or profile.total_tokens > 60000:
        size, overlap = 700, 100
        reasons.append(f"chunk_size 700: long sections (median {med} tokens) / large corpus")
    else:
        size, overlap = d.default_chunk_size, d.default_overlap
        reasons.append(f"chunk_size {size}: default for medium-length sections (median {med} tokens)")

    if profile.numeric_density > 0.06 or profile.tables:
        w = 0.5
        reasons.append(f"bm25_weight 0.5: many codes/numbers (density {profile.numeric_density}) or tables")
    else:
        w = 0.3
        reasons.append("bm25_weight 0.3: mostly prose, rely more on semantic search")

    n_docs = len(profile.documents)
    top_k = 8 if n_docs > 15 else (5 if n_docs <= 3 else d.default_top_k)
    reasons.append(f"top_k {top_k}: {n_docs} documents")
    return RetrievalCfg(chunk_size=size, chunk_overlap=overlap, embedder=cfg.llm.embedder, mode="hybrid", bm25_weight=w,
                        top_k=top_k, rerank=False, min_score=d.min_score, query_rewrite=False, reasons=reasons)
