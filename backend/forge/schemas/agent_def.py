"""The declarative agent definition (Req 3), saved as agent.yaml."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ToolName = Literal["csv_lookup", "calculator", "http_weather", "current_date"]
SLOT_NAMES = ("role", "audience", "tone", "scope", "refusal_policy", "grounding", "citation_rule", "tool_rules",
              "format")


class PromptSlots(BaseModel):
    role: str = "You are a helpful assistant."
    audience: str = ""
    tone: str = ""
    scope: str = ""
    refusal_policy: str = ""
    grounding: str = "Only state facts that appear in the provided context or tool results."
    citation_rule: str = "Cite every factual claim with a short verbatim quote from the context."
    tool_rules: str = ""
    format: str = ""


class FewShot(BaseModel):
    q: str
    a: str


class SystemPrompt(BaseModel):
    slots: PromptSlots = Field(default_factory=PromptSlots)
    few_shots: list[FewShot] = Field(default_factory=list, max_length=3)
    rendered: str = ""


class ModelCfg(BaseModel):
    provider: str = "ollama"
    name: str = "qwen2.5:7b-instruct"
    temperature: float = 0.0
    seed: int = 7
    max_tokens: int = 900


class RetrievalCfg(BaseModel):
    chunk_size: int = 600
    chunk_overlap: int = 90
    embedder: str = "BAAI/bge-small-en-v1.5"
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    bm25_weight: float = 0.4
    top_k: int = 6
    rerank: bool = False
    min_score: float = 0.25
    query_rewrite: bool = False
    reasons: list[str] = Field(default_factory=list)


class ToolBinding(BaseModel):
    name: ToolName
    reason: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class TableRef(BaseModel):
    name: str
    path: str


class CorpusRef(BaseModel):
    docs_dir: str = "docs"
    index_dir: str = "index"
    tables: list[TableRef] = Field(default_factory=list)


class OutputContract(BaseModel):
    json_schema_ref: str = "answer_v1"
    require_citations: bool = True
    max_words: int = 250


class Provenance(BaseModel):
    built_from_run: str = ""
    requirements_hash: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class AgentDefinition(BaseModel):
    schema_version: int = 1
    name: str = "Assistant"
    version: int = 1
    description: str = ""
    model: ModelCfg = Field(default_factory=ModelCfg)
    system_prompt: SystemPrompt = Field(default_factory=SystemPrompt)
    corpus: CorpusRef = Field(default_factory=CorpusRef)
    retrieval: RetrievalCfg = Field(default_factory=RetrievalCfg)
    tools: list[ToolBinding] = Field(default_factory=list)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    refusal_message: str = "I can't help with that based on the documents I have."
    suggested_questions: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)

    def tool_names(self) -> list[str]:
        return [t.name for t in self.tools]


def load_agent(path: str | Path) -> AgentDefinition:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AgentDefinition.model_validate(data)


def save_agent(agent: AgentDefinition, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(agent.model_dump(mode="json"), sort_keys=False, allow_unicode=True, width=110),
                 encoding="utf-8")


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = d
    return out


IGNORED_DIFF = {"version", "provenance.created_at", "system_prompt.rendered"}


def diff(a: AgentDefinition, b: AgentDefinition) -> list[dict[str, Any]]:
    """Field-level differences between two definitions (used by the change log)."""
    fa, fb = _flatten(a.model_dump(mode="json")), _flatten(b.model_dump(mode="json"))
    changes = []
    for key in sorted(set(fa) | set(fb)):
        if key in IGNORED_DIFF:
            continue
        if fa.get(key) != fb.get(key):
            changes.append({"path": key, "before": fa.get(key), "after": fb.get(key)})
    return changes
