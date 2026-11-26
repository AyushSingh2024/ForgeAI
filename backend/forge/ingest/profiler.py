"""Stage "ingest": load files, chunk, index, and build the CorpusProfile every later stage reasons about."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter

from pydantic import BaseModel

from forge.context import RunContext
from forge.errors import BadInput
from forge.ingest.chunker import chunk_documents
from forge.ingest.loaders import load_folder
from forge.ingest.tables import table_card_chunk
from forge.retrieval.bm25 import tokenize
from forge.retrieval.store import build_index
from forge.schemas.corpus import Chunk, CorpusProfile, DocProfile, Document
from forge.util import count_tokens, parse_numbers, write_json, write_jsonl

_EN_STOP = set("the and of to in is for that with on as are be this by or it from at an".split())
_HEAD_LINE = re.compile(r"^(#{1,6}\s+.+|(?:\d+\.)*\d+\.?\s+[A-Z].{1,80})$", re.MULTILINE)


class Summary(BaseModel):
    summary: str


def _keywords(chunks: list[Chunk], docs: list[Document], top: int = 8) -> dict[str, list[str]]:
    df: Counter[str] = Counter()
    per_doc: dict[str, Counter[str]] = {d.doc_id: Counter() for d in docs}
    for c in chunks:
        toks = [t for t in tokenize(c.text) if len(t) > 2 and not t.isdigit()]
        df.update(set(toks))
        if c.doc_id in per_doc:
            per_doc[c.doc_id].update(toks)
    n = max(1, len(chunks))
    out = {}
    for doc_id, tf in per_doc.items():
        scored = {t: f * math.log(1 + n / (1 + df[t])) for t, f in tf.items()}
        out[doc_id] = [t for t, _ in sorted(scored.items(), key=lambda kv: -kv[1])[:top]]
    return out


def _language(text: str) -> str:
    words = re.findall(r"[a-zA-Z]+", text.lower())[:3000]
    if not words:
        return "unknown"
    ratio = sum(w in _EN_STOP for w in words) / len(words)
    return "en" if ratio > 0.05 else "non-en"


def run_ingest(ctx: RunContext) -> CorpusProfile:
    docs_dir = ctx.docs_dir
    if not docs_dir.exists():
        raise BadInput(f"docs folder not found: {docs_dir}")
    documents, tables, warnings = load_folder(docs_dir)
    if not documents and not tables:
        raise BadInput("no usable documents or tables found in the docs folder. " + "; ".join(warnings))

    rcfg = ctx.cfg.retrieval
    chunks = chunk_documents(documents, rcfg.default_chunk_size, rcfg.default_overlap)
    chunks += [table_card_chunk(t) for t in tables]
    build_index(chunks, ctx.embedder(), ctx.path("index"), rcfg.default_chunk_size, rcfg.default_overlap)

    keywords = _keywords(chunks, documents)
    profiles = []
    for d in documents:
        full = "\n".join(p.text for p in d.pages)
        headings = [h.strip("# ").strip() for h in _HEAD_LINE.findall(full)][:25]
        summary = ""
        res = ctx.hub.builder.complete("doc_summary", {"title": d.title or d.doc_id, "text": full[:6000]},
                                       schema=Summary, max_tokens=200)
        if res.ok:
            summary = res.data.summary.strip()
        if not summary:
            summary = re.sub(r"\s+", " ", full.strip())[:200]
        profiles.append(DocProfile(doc_id=d.doc_id, title=d.title or d.doc_id, pages=len(d.pages), summary=summary,
                                   top_keywords=keywords.get(d.doc_id, []), headings=headings))

    all_text = " ".join(c.text for c in chunks)
    words = max(1, len(all_text.split()))
    section_tokens: Counter[str] = Counter()
    for c in chunks:
        section_tokens[(c.doc_id, tuple(c.section_path)).__repr__()] += c.token_count
    profile = CorpusProfile(
        documents=profiles, tables=tables, language=_language(all_text), total_tokens=count_tokens(all_text),
        n_chunks=len(chunks), numeric_density=round(len(parse_numbers(all_text)) / words, 4),
        median_section_tokens=int(statistics.median(section_tokens.values())) if section_tokens else 0,
        warnings=warnings)

    write_jsonl(ctx.path("corpus", "documents.jsonl"), documents)
    write_jsonl(ctx.path("corpus", "chunks.jsonl"), chunks)
    write_json(ctx.path("corpus_profile.json"), profile)
    ctx.emit("ingest", "info", f"{len(documents)} documents, {len(tables)} tables, {len(chunks)} chunks"
                               + (f", {len(warnings)} warnings" if warnings else ""))
    return profile
