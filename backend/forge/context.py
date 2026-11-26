"""RunContext: everything a stage needs (run folder, config, LLM clients, event callback)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.config import ForgeConfig
from forge.llm.client import LLMHub
from forge.retrieval.embedder import Embedder, get_embedder

EventFn = Callable[[str, str, str], None]


@dataclass
class RunContext:
    run_dir: Path
    cfg: ForgeConfig
    hub: LLMHub
    mode: str = "unattended"          # "interactive_cli" | "interactive_web" | "unattended"
    on_event: EventFn | None = None
    answers: dict[str, Any] | None = None   # interview answers (web) or answers.yaml content
    notes: list[str] = field(default_factory=list)

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    def path(self, *parts: str) -> Path:
        return self.run_dir.joinpath(*parts)

    @property
    def docs_dir(self) -> Path:
        return self.path("input", "docs")

    @property
    def brief(self) -> str:
        return self.path("input", "brief.txt").read_text(encoding="utf-8").strip()

    def embedder(self) -> Embedder:
        return get_embedder(self.cfg.llm.embedder)

    def retriever(self):
        """Retriever over the run's ingest index (default params). Used by the guard and the eval validator."""
        from forge.retrieval.hybrid import HybridRetriever
        from forge.schemas.agent_def import RetrievalCfg

        if getattr(self, "_retriever", None) is None:
            r = self.cfg.retrieval
            rc = RetrievalCfg(chunk_size=r.default_chunk_size, chunk_overlap=r.default_overlap,
                              embedder=self.cfg.llm.embedder, bm25_weight=r.bm25_weight, top_k=r.default_top_k,
                              min_score=r.min_score)
            self._retriever = HybridRetriever.from_index(self.path("index"), rc)
        return self._retriever

    def emit(self, stage: str, status: str, message: str = "") -> None:
        if self.on_event:
            self.on_event(stage, status, message)

    def note(self, text: str) -> None:
        """Record something the report must mention (fallbacks used, limits hit). Persisted across resumes."""
        self.notes.append(text)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.path("notes.txt").open("a", encoding="utf-8") as fh:
            fh.write(text.replace("\n", " ") + "\n")
