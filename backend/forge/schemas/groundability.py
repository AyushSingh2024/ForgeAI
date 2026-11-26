"""Output of the groundability guard (Req 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["supported", "partial", "unsupported", "needs_tool"]


class RetrievedRef(BaseModel):
    chunk_id: str
    score: float


class Probe(BaseModel):
    question: str
    retrieved: list[RetrievedRef] = Field(default_factory=list)
    supporting_quote: str | None = None
    supporting_chunk_id: str | None = None
    quote_verified: bool = False
    llm_said_supported: bool = False


class AskVerdict(BaseModel):
    ask_id: str
    ask_text: str
    source: Literal["brief", "must_answer"] = "must_answer"
    verdict: Verdict = "unsupported"
    needed_tool: str | None = None
    probes: list[Probe] = Field(default_factory=list)
    explanation: str = ""


class GroundabilityReport(BaseModel):
    verdicts: list[AskVerdict] = Field(default_factory=list)
    moved_to_refuse: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    coverage: float = 0.0


# LLM-facing helper schemas
class Ask(BaseModel):
    id: str
    text: str


class AskList(BaseModel):
    asks: list[Ask] = Field(default_factory=list)


class ProbeList(BaseModel):
    probes: list[str] = Field(default_factory=list)


class VerifyResult(BaseModel):
    reasoning: str = ""
    supported: bool = False
    chunk_id: str | None = None
    quote: str = ""
    missing: str = ""
    needs_tool: str | None = None
