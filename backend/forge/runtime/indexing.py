"""Build / refresh an agent's own index from its docs folder using the agent's retrieval params."""

from __future__ import annotations

from pathlib import Path

from forge.ingest.chunker import chunk_documents
from forge.ingest.loaders import load_folder
from forge.ingest.tables import table_card_chunk
from forge.retrieval.embedder import Embedder
from forge.retrieval.store import build_index, index_matches
from forge.schemas.agent_def import AgentDefinition


def docs_fingerprint(docs_dir: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    for p in sorted(docs_dir.rglob("*")):
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(docs_dir).parts):
            st = p.stat()
            h.update(f"{p.relative_to(docs_dir)}:{st.st_size}".encode())
    return h.hexdigest()[:16]


def build_agent_index(agent: AgentDefinition, agent_dir: Path, embedder: Embedder) -> int:
    r = agent.retrieval
    docs_dir = agent_dir / agent.corpus.docs_dir
    documents, tables, _ = load_folder(docs_dir)
    chunks = chunk_documents(documents, r.chunk_size, r.chunk_overlap) + [table_card_chunk(t) for t in tables]
    build_index(chunks, embedder, agent_dir / agent.corpus.index_dir, r.chunk_size, r.chunk_overlap,
                docs_sha=docs_fingerprint(docs_dir))
    return len(chunks)


def ensure_index(agent: AgentDefinition, agent_dir: Path, embedder: Embedder) -> bool:
    """Rebuild the index if it is missing or was built with other params. Returns True if rebuilt."""
    r = agent.retrieval
    idx = agent_dir / agent.corpus.index_dir
    docs_dir = agent_dir / agent.corpus.docs_dir
    if index_matches(idx, embedder.name, r.chunk_size, r.chunk_overlap, docs_fingerprint(docs_dir)):
        return False
    build_agent_index(agent, agent_dir, embedder)
    return True
